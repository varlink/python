# coding=utf-8

from __future__ import print_function
from __future__ import unicode_literals

import inspect
import json
import os
import socket
import stat
import string
import sys

from builtins import int
from builtins import object
from builtins import open
from builtins import range

from .error import (InterfaceNotFound, InvalidParameter, MethodNotImplemented, VarlinkEncoder, VarlinkError,
                    ConnectionError)
from .scanner import Interface

try:
    from socketserver import (StreamRequestHandler, BaseServer, ThreadingMixIn, ForkingMixIn)
except ImportError:  # Python2
    from SocketServer import (StreamRequestHandler, BaseServer, ThreadingMixIn, ForkingMixIn)

from types import GeneratorType


class Service(object):
    """Varlink service server handler

    To use the Service, a global object is instantiated:

        >>> service = Service(
        >>>    vendor='Red Hat',
        >>>    product='Manage System Accounts',
        >>>    version='1',
        >>>    interface_dir=os.path.dirname(__file__)
        >>> )

    For the class implementing the methods of a specific varlink interface
    a decorator is used:

        >>> @service.interface('com.redhat.system.accounts')
        >>> class Accounts:
        >>>     pass

    The varlink file corresponding to this interface is loaded from the 'interface_dir'
    specified in the constructor of the Service. It has to end in '.varlink'.

    Use a :class:`RequestHandler` with your Service object and run a :class:`Server` with it.

    If you want to use your own server with the Service object, split the incoming stream
    for every null byte and feed it to the :meth:`Service.handle` method.
    Write any message returned from this generator function to the output stream.

        >>> for outgoing_message in service.handle(incoming_message):
        >>>     connection.write(outgoing_message)


    Note: varlink only handles one method call at a time on one connection.

    """

    def __init__(self, vendor='', product='', version='', url='', interface_dir='.', namespaced=False):
        """Initialize the service with the data org.varlink.service.GetInfo() returns

        :param interface_dir: the directory with the \*.varlink files for the interfaces

        """
        self.vendor = vendor
        self.product = product
        self.version = version
        self.url = url
        self.interface_dir = interface_dir
        self._namespaced = namespaced

        self.interfaces = {}
        self.interfaces_handlers = {}
        directory = os.path.dirname(__file__)
        self._add_interface(os.path.join(directory, 'org.varlink.service.varlink'), self)

    def GetInfo(self):
        """The standardized org.varlink.service.GetInfo() varlink method."""
        return {
            'vendor': self.vendor,
            'product': self.product,
            'version': self.version,
            'url': self.url,
            'interfaces': list(self.interfaces.keys())
        }

    def GetInterfaceDescription(self, interface):
        """The standardized org.varlink.service.GetInterfaceDescription() varlink method."""
        try:
            i = self.interfaces[interface]
        except KeyError:
            raise InterfaceNotFound(interface)

        return {'description': i.description}

    def _handle(self, message, raw_message, _server=None, _request=None):
        try:
            interface_name, _, method_name = message.get('method', '').rpartition('.')
            if not interface_name or not method_name:
                raise InterfaceNotFound(interface_name)

            interface = self.interfaces.get(interface_name)
            if not interface:
                raise InterfaceNotFound(interface_name)

            method = interface.get_method(method_name)

            parameters = message.get('parameters', {})
            if parameters == None:
                parameters = {}

            handler = self.interfaces_handlers[interface.name]

            for name in parameters:
                if name not in method.in_type.fields:
                    raise InvalidParameter(name)

            for name in method.in_type.fields:
                if name not in parameters:
                    parameters[name] = None

            parameters = interface.filter_params("server.call", method.in_type, self._namespaced, parameters, None)

            func = getattr(handler, method_name, None)

            if not func or not callable(func):
                raise MethodNotImplemented(method_name)

            kwargs = {}

            if hasattr(inspect, "signature"):
                sig = inspect.signature(func)
                arg_names = [(sig.parameters[k].kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY) and k or None) for k in
                             sig.parameters.keys()]
            else:
                from itertools import izip
                spec = inspect.getargspec(func)
                matched_args = [reversed(x) for x in [spec.args, spec.defaults or []]]
                arg_names = dict(izip(*matched_args))

            if message.get('more', False) or message.get('oneway', False) or message.get('upgrade', False):
                if message.get('more', False) and '_more' in arg_names:
                    kwargs["_more"] = True

                if message.get('oneway', False) and '_oneway' in arg_names:
                    kwargs["_oneway"] = True

                if message.get('upgrade', False) and '_upgrade' in arg_names:
                    kwargs["_upgrade"] = True

            if '_raw' in arg_names:
                kwargs["_raw"] = raw_message
            if '_message' in arg_names:
                kwargs["_message"] = message
            if '_interface' in arg_names:
                kwargs["_interface"] = interface
            if '_method' in arg_names:
                kwargs["_method"] = method
            if '_server' in arg_names:
                kwargs["_server"] = _server
            if '_request' in arg_names:
                kwargs["_request"] = _request

            if self._namespaced:
                out = func(*(getattr(parameters, k) for k in method.in_type.fields.keys()), **kwargs)
            else:
                out = func(*(parameters[k] for k in method.in_type.fields.keys()), **kwargs)

            if isinstance(out, GeneratorType):
                try:
                    for o in out:
                        if isinstance(o, Exception):
                            raise o

                        if kwargs.get("_oneway", False):
                            continue

                        cont = True
                        if '_continues' in o:
                            cont = o['_continues']
                            del o['_continues']
                            yield {'continues': bool(cont),
                                   'parameters': interface.filter_params("server.reply", method.out_type,
                                                                         self._namespaced, o,
                                                                         None) or {}}
                        else:
                            yield {'parameters': interface.filter_params("server.reply", method.out_type,
                                                                         self._namespaced, o,
                                                                         None) or {}}

                        if not cont:
                            return
                except ConnectionError as e:
                    try:
                        out.throw(e)
                    except StopIteration:
                        pass
            else:
                if message.get('oneway', False):
                    yield None
                else:
                    yield {'parameters': out or {}}

        except VarlinkError as error:
            yield error

    def handle(self, message, _server=None, _request=None):
        """This generator function handles any incoming message.

        Write any returned bytes to the output stream.

            >>> for outgoing_message in service.handle(incoming_message):
            >>>    connection.write(outgoing_message)
        """
        if not message:
            return

        if message[-1] == 0:
            message = message[:-1]

        handle = self._handle(json.loads(message), message, _server, _request)
        for out in handle:
            if out == None:
                return
            try:
                yield json.dumps(out, cls=VarlinkEncoder).encode('utf-8')
            except ConnectionError as e:
                try:
                    handle.throw(e)
                except StopIteration:
                    pass

    def _add_interface(self, filename, handler):
        if not os.path.isabs(filename):
            filename = os.path.join(self.interface_dir, filename + '.varlink')

        with open(filename) as f:
            interface = Interface(f.read())
            self.interfaces[interface.name] = interface
            self.interfaces_handlers[interface.name] = handler

    def interface(self, filename):

        def decorator(interface_class):
            self._add_interface(filename, interface_class())
            return interface_class

        return decorator


def get_listen_fd():
    if "LISTEN_FDS" not in os.environ:
        return None
    if "LISTEN_PID" not in os.environ:
        return None
    try:
        if int(os.environ["LISTEN_PID"]) != os.getpid():
            return None
    except:
        return None

    try:
        fds = int(os.environ["LISTEN_FDS"])
    except:
        return None

    if fds < 1:
        return None

    if fds == 1:
        try:
            if stat.S_ISSOCK(os.fstat(3).st_mode):
                return 3
            else:
                return None
        except OSError:
            return None

    fields = string.split(os.environ["LISTEN_FDNAMES"], ":")

    if len(fields) != fds:
        return None

    for i in range(len(fields)):
        if fields[i] == "varlink":
            try:
                if stat.S_ISSOCK(os.fstat(i + 3).st_mode):
                    return i + 3
                else:
                    return None
            except OSError:
                return None


class RequestHandler(StreamRequestHandler):
    """Varlink request handler

    To use as an argument for the VarlinkServer constructor.
    Instantiate your own class and set the class variable service to your global :class:`Service` object.
    """
    service = None

    def handle(self):
        message = b''

        self.request.setblocking(True)
        while not self.rfile.closed:
            c = self.rfile.read(1)

            if c == b'':
                break

            if c != b'\0':
                message += c
                continue

            for reply in self.service.handle(message, _server=self.server, _request=self.request):
                if reply != None:
                    self.wfile.write(reply + b'\0')

            message = b''


class Server(BaseServer):
    """Server

    The same as the standard socketserver.TCPServer, to initialize with a subclass of :class:`RequestHandler`.

        >>> import varlink
        >>> import os
        >>>
        >>> service = varlink.Service(vendor='Example', product='Examples', version='1', url='http://example.com',
        >>>    interface_dir=os.path.dirname(__file__))
        >>>
        >>> class ServiceRequestHandler(varlink.RequestHandler):
        >>>    service = service
        >>>
        >>> @service.interface('com.example.service')
        >>> class Example:
        >>>    # com.example.service method implementation here …
        >>>    pass
        >>>
        >>> server = varlink.ThreadingServer(sys.argv[1][10:], ServiceRequestHandler)
        >>> server.serve_forever()
    """

    address_family = socket.AF_INET

    socket_type = socket.SOCK_STREAM

    request_queue_size = 5

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        self.remove_file = None
        self.mode = None
        self.listen_fd = get_listen_fd()

        if self.listen_fd:
            server_address = self.listen_fd
            self.address_family = socket.AF_UNIX
            self.socket = socket.fromfd(self.listen_fd, socket.AF_UNIX, socket.SOCK_STREAM)

        elif server_address.startswith("unix:"):
            self.address_family = socket.AF_UNIX
            address = server_address[5:]
            m = address.rfind(';mode=')
            if m != -1:
                self.mode = address[m + 6:]
                address = address[:m]

            if address[0] == '@':
                address = address.replace('@', '\0', 1)
                self.mode = None
            else:
                self.remove_file = address

            server_address = address
            self.socket = socket.socket(self.address_family, self.socket_type)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        elif server_address.startswith("tcp:"):
            address = server_address[4:]
            p = address.rfind(':')
            if p != -1:
                port = int(address[p + 1:])
                address = address[:p]
            else:
                raise ConnectionError("Invalid address 'tcp:%s'" % address)
            address = address.replace('[', '')
            address = address.replace(']', '')

            try:
                res = socket.getaddrinfo(address, port, proto=socket.IPPROTO_TCP, flags=socket.AI_NUMERICHOST)
            except TypeError:
                res = socket.getaddrinfo(address, port, self.address_family, self.socket_type, socket.IPPROTO_TCP,
                                         socket.AI_NUMERICHOST)

            af, socktype, proto, canonname, sa = res[0]
            self.address_family = af
            self.socket_type = socktype
            self.socket = socket.socket(self.address_family, self.socket_type)
            server_address = sa[0:2]

        else:
            raise ConnectionError("Invalid address '%s'" % server_address)

        BaseServer.__init__(self, server_address, RequestHandlerClass)

        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except:
                self.server_close()
                raise

    def server_bind(self):
        """Called by constructor to bind the socket.

        May be overridden.

        """
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(True)

        if not self.listen_fd:
            self.socket.bind(self.server_address)

        self.server_address = self.socket.getsockname()

        if self.server_address[0] == 0:
            self.server_address = '@' + self.server_address[1:].decode('utf-8')
        elif self.mode:
            os.chmod(self.server_address, mode=int(self.mode, 8))

    def server_activate(self):
        """Called by constructor to activate the server.

        May be overridden.

        """
        self.socket.listen(self.request_queue_size)

    def server_close(self):
        """Called to clean-up the server.

        May be overridden.

        """
        if self.remove_file:
            try:
                os.remove(self.remove_file)
            except:
                pass
        self.socket.close()

    def fileno(self):
        """Return socket file number.

        Interface required by selector.

        """
        return self.socket.fileno()

    def get_request(self):
        """Get the request and client address from the socket.

        May be overridden.

        """
        return self.socket.accept()

    def shutdown_request(self, request):
        """Called to shutdown and close an individual request."""
        try:
            # explicitly shutdown.  socket.close() merely releases
            # the socket and waits for GC to perform the actual close.
            request.shutdown(socket.SHUT_RDWR)

        except:
            pass  # some platforms may raise ENOTCONN here
        self.close_request(request)

    def close_request(self, request):
        """Called to clean up an individual request."""
        request.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.server_close()


class ThreadingServer(ThreadingMixIn, Server): pass


class ForkingServer(ForkingMixIn, Server): pass
