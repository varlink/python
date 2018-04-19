#!/usr/bin/python3

"""An implementation of the varlink protocol

See http://varlink.org for more information about the varlink protocol and interface definition files.

For service implementations use the Server() class, for client implementations use the Client() class.
"""

import json
import os
import re
import signal
import socket
import stat
import string
import sys
import traceback
from inspect import (signature, Parameter)
from socketserver import (StreamRequestHandler, BaseServer, ThreadingMixIn, ForkingMixIn)
from types import (SimpleNamespace, GeneratorType)

import collections


class VarlinkEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, set):
            return dict.fromkeys(o, {})
        if isinstance(o, SimpleNamespace):
            return o.__dict__
        if isinstance(o, VarlinkError):
            return o.as_dict()
        return json.JSONEncoder.default(self, o)


class VarlinkError(Exception):
    """The base class for varlink error exceptions"""

    def __init__(self, message, namespaced=False):
        if not namespaced and not isinstance(message, dict):
            raise TypeError
        # normalize to dictionary
        super().__init__(json.loads(json.dumps(message, cls=VarlinkEncoder)))

    def error(self):
        """returns the exception varlink error name"""
        return self.args[0].get('error')

    def parameters(self, namespaced=False):
        """returns the exception varlink error parameters"""
        if namespaced:
            return json.loads(json.dumps(self.args[0]['parameters']), object_hook=lambda d: SimpleNamespace(**d))
        else:
            return self.args[0].get('parameters')

    def as_dict(self):
        return self.args[0]


class InterfaceNotFound(VarlinkError):
    """The standardized varlink InterfaceNotFound error as a python exception"""

    def __init__(self, interface):
        VarlinkError.__init__(self, {'error': 'org.varlink.service.InterfaceNotFound',
                                     'parameters': {'interface': interface}})


class MethodNotFound(VarlinkError):
    """The standardized varlink MethodNotFound error as a python exception"""

    def __init__(self, method):
        VarlinkError.__init__(self, {'error': 'org.varlink.service.MethodNotFound', 'parameters': {'method': method}})


class MethodNotImplemented(VarlinkError):
    """The standardized varlink MethodNotImplemented error as a python exception"""

    def __init__(self, method):
        VarlinkError.__init__(self,
                              {'error': 'org.varlink.service.MethodNotImplemented', 'parameters': {'method': method}})


class InvalidParameter(VarlinkError):
    """The standardized varlink InvalidParameter error as a python exception"""

    def __init__(self, name):
        VarlinkError.__init__(self,
                              {'error': 'org.varlink.service.InvalidParameter', 'parameters': {'parameter': name}})


class ClientInterfaceHandler:
    """Base class for varlink client, which wraps varlink methods of an interface to the class"""

    def __init__(self, interface, namespaced=False):
        """Base class for varlink client, which wraps varlink methods of an interface.

        The object allows to talk to a varlink service, which implements the specified interface
        transparently by calling the methods. The call blocks until enough messages are received.

        For monitor calls with '_more=True' a generator object is returned.

        Arguments:
        interface - an Interface object
        namespaced - if True, varlink methods return SimpleNamespace objects instead of dictionaries
        """
        if not isinstance(interface, Interface):
            raise TypeError

        self._interface = interface
        self._namespaced = namespaced
        self._in_use = False

        for member in interface.members.values():
            if isinstance(member, _Method):
                self._add_method(member)

    def close(self):
        """To be implemented."""
        raise NotImplementedError

    def _send_message(self, out):
        """To be implemented.

        This should send a varlink message to the varlink service adding a trailing zero byte.
        """
        raise NotImplementedError

    def _next_message(self):
        """To be implemented.

        This must be a generator yielding the next received varlink message without the trailing zero byte.
        """
        raise NotImplementedError

    def _add_method(self, method):

        def _wrapped(*args, **kwargs):
            if "_more" in kwargs and kwargs.pop("_more"):
                return self._call_more(method.name, *args, **kwargs)
            else:
                return self._call(method.name, *args, **kwargs)

        _wrapped.__name__ = method.name
        # FIXME: add comments
        if method.signature:
            _wrapped.__doc__ = "Varlink call: " + method.signature
        setattr(self, method.name, _wrapped)

    def _next_varlink_message(self):
        message = next(self._next_message())

        message = json.loads(message)
        if not 'parameters' in message:
            message['parameters'] = {}

        if 'error' in message and message["error"] != None:
            raise VarlinkError(message, self._namespaced)
        else:
            return message['parameters'], ('continues' in message) and message['continues']

    def _call(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError("Tried to call a varlink method, while other call still in progress")

        oneway = False
        if "_oneway" in kwargs and kwargs.pop("_oneway"):
            oneway = True

        method = self._interface.get_method(method_name)

        parameters = self._interface.filter_params(method.in_type, False, args, kwargs)
        if oneway:
            out = {'oneway': True, 'method': self._interface.name + "." + method_name, 'parameters': parameters}
        else:
            out = {'method': self._interface.name + "." + method_name, 'parameters': parameters}
        self._send_message(json.dumps(out, cls=VarlinkEncoder).encode('utf-8'))

        if oneway:
            return None

        self._in_use = True
        (message, more) = self._next_varlink_message()
        if more:
            self.close()
            self._in_use = False
            raise ConnectionError("Server indicated more varlink messages")
        self._in_use = False

        if message:
            message = self._interface.filter_params(method.out_type, self._namespaced, message, None)

        return message

    def _call_more(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError("Tried to call a varlink method, while other call still in progress")

        method = self._interface.get_method(method_name)

        parameters = self._interface.filter_params(method.in_type, False, args, kwargs)
        out = {'method': self._interface.name + "." + method_name, 'more': True, 'parameters': parameters}

        self._send_message(json.dumps(out, cls=VarlinkEncoder).encode('utf-8'))

        more = True
        self._in_use = True
        while more:
            (message, more) = self._next_varlink_message()
            if message:
                message = self._interface.filter_params(method.out_type, self._namespaced, message, None)
            yield message
        self._in_use = False


class SimpleClientInterfaceHandler(ClientInterfaceHandler):
    """A varlink client for an interface doing send/write and receive/read on a socket or file stream"""

    def __init__(self, interface, file_or_socket, namespaced=False):
        """Creates an object with the varlink methods of an interface installed.

        The object allows to talk to a varlink service, which implements the specified interface
        transparently by calling the methods. The call blocks until enough messages are received.

        For monitor calls with '_more=True' a generator object is returned.

        Arguments:
        interface - an Interface object
        file_or_socket - an open socket or io stream
        namespaced - if True, varlink methods return SimpleNamespace objects instead of dictionaries
        """
        super().__init__(interface, namespaced=namespaced)
        self._connection = file_or_socket

        if hasattr(self._connection, 'sendall'):
            self._sendall = True
        else:
            if not hasattr(self._connection, 'write'):
                raise TypeError
            self._sendall = False

        if hasattr(self._connection, 'recv'):
            self._recv = True
        else:
            if not hasattr(self._connection, 'read'):
                raise TypeError
            self._recv = False

        self._in_buffer = b''

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def close(self):
        try:
            if hasattr(self._connection, 'shutdown'):
                self._connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        self._connection.close()

    def _send_message(self, out):
        if self._sendall:
            self._connection.sendall(out + b'\0')
        elif hasattr:
            self._connection.write(out + b'\0')

    def _next_message(self):
        while True:
            message, sep, self._in_buffer = self._in_buffer.partition(b'\0')
            if not sep:
                # No zero byte found
                self._in_buffer = message
                message = None

            if message:
                yield message
                continue

            if self._recv:
                data = self._connection.recv(8192)
            else:
                data = self._connection.read(8192)

            if len(data) == 0:
                raise BrokenPipeError("Disconnected")
            self._in_buffer += data


class Client:
    """Varlink client class.

    >>> from varlink import Client
    >>> client = Client(resolve_interface='io.systemd.journal')
    >>> print(client.get_interfaces()['io.systemd.journal'].get_description())
    # Query and monitor the log messages of a system.
    interface io.systemd.journal

    type Entry (cursor: string, time: string, message: string, process: string, priority: string)

    # Monitor the log. Returns the @initial_lines most recent entries in the
    # first reply and then continuously replies when new entries are available.
    method Monitor(initial_lines: int) -> (entries: Entry[])
    >>>
    >>> connection = client.open("io.systemd.journal")

    connection now holds an object with all the varlink methods available.

    Do varlink method call with varlink arguments and a
    single varlink return structure wrapped in a namespace class:
    >>> ret = connection.Monitor(initial_lines=1)
    >>> ret
    namespace(entries=[namespace(cursor='s=[…]',
       message="req:1 'dhcp4-change' [wlp3s0][…]", priority='critical',
       process='nm-dispatcher', time='2018-01-29 12:19:59Z')])
    >>> ret.entries[0].process
    'nm-dispatcher'

    Do varlink method call with varlink arguments and a
    multiple return values in monitor mode, using the "_more" keyword:
    >>> for m in connection.Monitor(_more=True):
    >>>     for e in m.entries:
    >>>         print("%s: %s" % (e.time, e.message))
    2018-01-29 12:19:59Z: [system] Activating via systemd: service name='[…]
    2018-01-29 12:19:59Z: Starting Network Manager Script Dispatcher Service...
    2018-01-29 12:19:59Z: bound to 10.200.159.150 -- renewal in 1423 seconds.
    2018-01-29 12:19:59Z: [system] Successfully activated service 'org.freedesktop.nm_dispatcher'
    2018-01-29 12:19:59Z: Started Network Manager Script Dispatcher Service.
    2018-01-29 12:19:59Z: req:1 'dhcp4-change' [wlp3s0]: new request (6 scripts)
    2018-01-29 12:19:59Z: req:1 'dhcp4-change' [wlp3s0]: start running ordered scripts...

    "_more" is special to this python varlink binding. If "_more=True", then the method call does
    not return a normal namespace wrapped varlink return value, but a generator,
    which yields the return values and waits (blocks) for the service to return more return values
    in the generator's .__next__() call.
    """
    handler = SimpleClientInterfaceHandler

    def __init__(self, address=None, resolve_interface=None, resolver=None):
        """Get the interface descriptions from a varlink service.

        Keyword arguments:
        address -- the exact address like "unix:/run/org.varlink.resolver"
        resolve_interface -- an interface name, which is resolved with the system wide resolver
        resolver -- the exact address of the resolver to be used to resolve the interface name

        Exceptions:
        ConnectionError - could not connect to the service or resolver
        """
        self._interfaces = {}
        self._child_pid = 0
        self.port = None
        self.address = None

        def _resolve_interface(_interface, _resolver):
            resolver_connection = Client(_resolver).open('org.varlink.resolver')
            # noinspection PyUnresolvedReferences
            _r = resolver_connection.Resolve(_interface)
            return _r['address']

        with open(os.path.join(os.path.dirname(__file__), 'org.varlink.service.varlink')) as f:
            interface = Interface(f.read())
            self.add_interface(interface)

        if address is None and not (resolve_interface is None):
            address = _resolve_interface(resolve_interface, resolver or "unix:/run/org.varlink.resolver")

        if address.startswith("unix:"):
            address = address[5:]
            mode = address.rfind(';mode=')
            if mode != -1:
                address = address[:mode]
            if address[0] == '@':
                address = address.replace('@', '\0', 1)
        elif address.startswith("exec:"):
            executable = address[5:]
            s = socket.socket(socket.AF_UNIX)
            s.setblocking(False)
            s.bind("")
            s.listen()
            address = s.getsockname().decode('ascii')

            self._child_pid = os.fork()
            if self._child_pid == 0:
                # child
                n = s.fileno()
                if n == 3:
                    # without dup() the socket is closed with the python destructor
                    n = os.dup(3)
                    del s
                else:
                    try:
                        os.close(3)
                    except OSError:
                        pass

                os.dup2(n, 3)
                address = address.replace('\0', '@', 1)
                address = "--varlink=unix:%s;mode=0600" % address
                os.environ["LISTEN_FDS"] = "1"
                os.environ["LISTEN_FDNAMES"] = "varlink"
                os.environ["LISTEN_PID"] = str(os.getpid())
                os.execlp(executable, executable, address)
                sys.exit(1)
            # parent
            s.close()
        elif address.startswith("tcp:"):
            address = address[4:]
            p = address.rfind(':')
            if p != -1:
                port = address[p + 1:]
                address = address[:p]
            else:
                raise ConnectionError("Invalid address 'tcp:%s'" % address)
            address = address.replace('[', '')
            address = address.replace(']', '')
            self.port = port
        else:
            # FIXME: also accept other transports
            raise ConnectionError("Invalid address '%s'" % address)

        self.address = address
        _connection = self.open("org.varlink.service")
        # noinspection PyUnresolvedReferences
        info = _connection.GetInfo()

        for interface_name in info['interfaces']:
            # noinspection PyUnresolvedReferences
            desc = _connection.GetInterfaceDescription(interface_name)
            interface = Interface(desc['description'])
            self._interfaces[interface.name] = interface
        _connection.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, value, _traceback):
        if hasattr(self, "_child_pid") and self._child_pid != 0:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except OSError:
                pass
            os.waitpid(self._child_pid, 0)

    def open(self, interface_name, namespaced=False):
        """Open a new connection and get a client interface handle with the varlink methods installed.

        Arguments:
        interface_name -- an interface name, which the service this client object is
                          connected to, provides.

        Exceptions:
        InterfaceNotFound -- if the interface is not found
        anything socket.connect() throws
        """

        if interface_name not in self._interfaces:
            raise InterfaceNotFound(interface_name)

        if self.port:
            s = socket.create_connection((self.address, self.port))
        else:
            s = socket.socket(socket.AF_UNIX)
            s.setblocking(True)
            s.connect(self.address)

        return self.handler(self._interfaces[interface_name], s, namespaced=namespaced)

    def get_interfaces(self):
        """Returns the a list of Interface objects the service implements."""
        return self._interfaces

    def add_interface(self, interface):
        """Manually add or overwrite an interface definition from an Interface object.

        Argument:
        interface - an Interface() object
        """
        if not isinstance(interface, Interface):
            raise TypeError

        self._interfaces[interface.name] = interface


class Service:
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
    @service.interface('com.redhat.system.accounts')
    class Accounts:
    […]

    The varlink file corresponding to this interface is loaded from the 'interface_dir'
    specified in the constructor of the Service. It has to end in '.varlink'.

    Split the incoming stream for every null byte and feed it to the service.handle()
    function. Write any message returned from this generator function to the output stream.
    for outgoing_message in service.handle(incoming_message):
        connection.write(outgoing_message)

    or see, how the SimpleServer handles the Service object:
    SimpleServer(service).serve(sys.argv[1], listen_fd=listen_fd)

    Note: varlink only handles one method call at a time on one connection.

    """

    def __init__(self, vendor='', product='', version='', url='', interface_dir='.', namespaced=False):
        """Initialize the service with the data org.varlink.service.GetInfo() returns

        Arguments:
        interface_dir -- the directory with the *.varlink files for the interfaces
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
            handler = self.interfaces_handlers[interface.name]

            for name in parameters:
                if name not in method.in_type.fields:
                    raise InvalidParameter(name)

            parameters = interface.filter_params(method.in_type, self._namespaced, parameters, None)

            func = getattr(handler, method_name, None)

            if not func or not callable(func):
                raise MethodNotImplemented(method_name)

            kwargs = {}
            sig = signature(func)

            if message.get('more', False) or message.get('oneway', False) or message.get('upgrade', False):
                if message.get('more', False) and '_more' in sig.parameters \
                        and sig.parameters["_more"].kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                    kwargs["_more"] = True

                if message.get('oneway', False) and '_oneway' in sig.parameters \
                        and sig.parameters["_oneway"].kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                    kwargs["_oneway"] = True

                if message.get('upgrade', False) and '_upgrade' in sig.parameters \
                        and sig.parameters["_upgrade"].kind in \
                        (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                    kwargs["_upgrade"] = True

            if '_raw' in sig.parameters and sig.parameters["_raw"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                kwargs["_raw"] = raw_message
            if '_message' in sig.parameters and sig.parameters["_message"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                kwargs["_message"] = message
            if '_interface' in sig.parameters and sig.parameters["_interface"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                kwargs["_interface"] = interface
            if '_method' in sig.parameters and sig.parameters["_method"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                kwargs["_method"] = method
            if '_server' in sig.parameters and sig.parameters["_server"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
                kwargs["_server"] = _server
            if '_request' in sig.parameters and sig.parameters["_request"].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
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
                            yield {'continues': bool(cont), 'parameters': interface.filter_params(method.out_type,
                                                                                                  self._namespaced, o,
                                                                                                  None) or {}}
                        else:
                            yield {'parameters': interface.filter_params(method.out_type,
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
                if kwargs.get("_oneway", False):
                    return
                else:
                    yield {'parameters': out or {}}

        except VarlinkError as error:
            yield error
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__)
            yield {'error': 'InternalError'}

    def handle(self, message, _server=None, _request=None):
        """This generator function handles any incoming message. Write any returned bytes to the output stream.

        for outgoing_message in service.handle(incoming_message):
            connection.write(outgoing_message)
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


class Interface:
    """Class for a parsed varlink interface definition."""

    def __init__(self, description):
        """description -- description string in varlink interface definition language"""
        self.description = description

        scanner = Scanner(description)
        scanner.expect('interface')
        self.name = scanner.expect('interface-name')
        self.members = collections.OrderedDict()
        while not scanner.end():
            member = scanner.read_member()
            self.members[member.name] = member

    def get_description(self):
        """return the description string in varlink interface definition language"""
        return self.description

    def get_method(self, name):
        method = self.members.get(name)
        if method and isinstance(method, _Method):
            return method
        raise MethodNotFound(name)

    def filter_params(self, varlink_type, _namespaced, args, kwargs):
        # print("filter_params", type(varlink_type), repr(varlink_type), args, kwargs)

        if isinstance(varlink_type, _Maybe):
            if args == None:
                return None
            return self.filter_params(varlink_type.element_type, _namespaced, args, kwargs)

        if isinstance(varlink_type, _Dict):
            if isinstance(args, dict):
                for (k, v) in args.items():
                    args[k] = self.filter_params(varlink_type.element_type, _namespaced, v, None)
                return args
            else:
                SyntaxError("Expected dict, got %s", args)

        if isinstance(varlink_type, _CustomType):
            # print("CustomType", varlink_type.name)
            return self.filter_params(self.members.get(varlink_type.name), _namespaced, args, kwargs)

        if isinstance(varlink_type, _Alias):
            # print("Alias", varlink_type.name)
            return self.filter_params(varlink_type.type, _namespaced, args, kwargs)

        if isinstance(varlink_type, _Object):
            return args

        if isinstance(varlink_type, _Enum) and isinstance(args, str):
            # print("Returned str:", args)
            return args

        if isinstance(varlink_type, _Array):
            return [self.filter_params(varlink_type.element_type, _namespaced, x, None) for x in args]

        if isinstance(varlink_type, set):
            # print("Returned set:", set(args))
            return set(args)

        if isinstance(varlink_type, str) and isinstance(args, str):
            # print("Returned str:", args)
            return args

        if isinstance(varlink_type, float) and isinstance(args, float):
            # print("Returned float:", args)
            return args

        if isinstance(varlink_type, bool) and isinstance(args, bool):
            # print("Returned bool:", args)
            return args

        if isinstance(varlink_type, int) and isinstance(args, int):
            # print("Returned int:", args)
            return args

        if not isinstance(varlink_type, _Struct):
            raise SyntaxError("Expected type %s, got %s with value '%s'" % (type(varlink_type), type(args),
                                                                            args))
        if _namespaced:
            out = SimpleNamespace()
        else:
            out = {}

        varlink_struct = None
        if not isinstance(args, tuple):
            varlink_struct = args
            args = None

        for name in varlink_type.fields:
            if isinstance(args, tuple):
                if args:
                    val = args[0]
                    if len(args) > 1:
                        args = args[1:]
                    else:
                        args = None
                    ret = self.filter_params(varlink_type.fields[name], _namespaced, val, None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                    continue
                else:
                    if name in kwargs:
                        ret = self.filter_params(varlink_type.fields[name], _namespaced, kwargs[name], None)
                        if ret != None:
                            # print("SetOUT:", name)
                            if _namespaced:
                                setattr(out, name, ret)
                            else:
                                out[name] = ret
                        continue

            if varlink_struct:
                if isinstance(varlink_struct, dict):
                    if name not in varlink_struct:
                        continue

                    val = varlink_struct[name]
                    ret = self.filter_params(varlink_type.fields[name], _namespaced, val, None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                elif hasattr(varlink_struct, name):
                    val = getattr(varlink_struct, name)
                    ret = self.filter_params(varlink_type.fields[name], _namespaced, val, None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                else:
                    continue

        return out


class Scanner:
    """Class for scanning a varlink interface definition."""

    def __init__(self, string):
        self.whitespace = re.compile(r'([ \t\n]|#.*$)+', re.ASCII | re.MULTILINE)
        # FIXME: nested ()
        self.method_signature = re.compile(r'([ \t\n]|#.*$)*(\([^)]*\))([ \t\n]|#.*$)*->([ \t\n]|#.*$)*(\([^)]*\))',
                                           re.ASCII | re.MULTILINE)

        self.keyword_pattern = re.compile(r'\b[a-z]+\b|[:,(){}]|->|\[\]|\?|\[string\]\(\)|\[string\]', re.ASCII)
        self.patterns = {
            'interface-name': re.compile(r'[a-z]+(\.[a-z0-9][a-z0-9-]*)+'),
            'member-name': re.compile(r'\b[A-Z][A-Za-z0-9_]*\b', re.ASCII),
            'identifier': re.compile(r'\b[a-z][A-Za-z0-9_]*\b', re.ASCII),
        }

        self.string = string
        self.pos = 0

    def get(self, expected):
        m = self.whitespace.match(self.string, self.pos)
        if m:
            self.pos = m.end()

        pattern = self.patterns.get(expected)
        if pattern:
            m = pattern.match(self.string, self.pos)
            if m:
                self.pos = m.end()
                return m.group(0)
        else:
            m = self.keyword_pattern.match(self.string, self.pos)
            if m and m.group(0) == expected:
                self.pos = m.end()
                return True

    def expect(self, expected):
        value = self.get(expected)
        if not value:
            raise SyntaxError("expected '{}'".format(expected))
        return value

    def end(self):
        m = self.whitespace.match(self.string, self.pos)
        if m:
            self.pos = m.end()

        return self.pos >= len(self.string)

    def read_type(self, lastmaybe=False):
        if self.get('?'):
            if lastmaybe:
                raise SyntaxError("double '??'")
            return _Maybe(self.read_type(lastmaybe=True))

        if self.get('[string]()'):
            return set()

        if self.get('[string]'):
            return _Dict(self.read_type())

        if self.get('[]'):
            return _Array(self.read_type())

        if self.get('object'):
            return _Object()

        if self.get('bool'):
            t = bool()
        elif self.get('int'):
            t = int()
        elif self.get('float'):
            t = float()
        elif self.get('string'):
            t = str()
        else:
            name = self.get('member-name')
            if name:
                t = _CustomType(name)
            else:
                t = self.read_struct()

        return t

    def read_struct(self):
        _isenum = None
        self.expect('(')
        fields = collections.OrderedDict()
        if not self.get(')'):
            while True:
                name = self.expect('identifier')
                if _isenum == None:
                    if self.get(':'):
                        _isenum = False
                        fields[name] = self.read_type()
                        if not self.get(','):
                            break
                        continue
                    elif self.get(','):
                        _isenum = True
                        fields[name] = True
                        continue
                    else:
                        raise SyntaxError("after '{}'".format(name))
                elif not _isenum:
                    try:
                        self.expect(':')
                        fields[name] = self.read_type()
                    except SyntaxError as e:
                        raise SyntaxError("after '{}': {}".format(name, e))
                else:
                    fields[name] = True

                if not self.get(','):
                    break
            self.expect(')')
        if _isenum:
            return _Enum(fields.keys())
        else:
            return _Struct(fields)

    def read_member(self):
        if self.get('type'):
            try:
                _name = self.expect('member-name')
            except SyntaxError:
                m = self.whitespace.match(self.string, self.pos)
                if m:
                    start = m.end()
                else:
                    start = self.pos
                m = self.whitespace.search(self.string, start)
                if m:
                    stop = m.start()
                else:
                    stop = start

                raise SyntaxError("'{}' not a valid type name.".format(self.string[start:stop]))
            try:
                _type = self.read_type()
            except SyntaxError as e:
                raise SyntaxError("in '{}': {}".format(_name, e))
            return _Alias(_name, _type)
        elif self.get('method'):
            name = self.expect('member-name')
            # FIXME
            sig = self.method_signature.match(self.string, self.pos)
            if sig:
                sig = name + sig.group(0)
            in_type = self.read_struct()
            self.expect('->')
            out_type = self.read_struct()
            return _Method(name, in_type, out_type, sig)
        elif self.get('error'):
            return _Error(self.expect('member-name'), self.read_type())
        else:
            raise SyntaxError('expected type, method, or error')


class _Object:
    pass


class _Struct:

    def __init__(self, fields):
        self.fields = collections.OrderedDict(fields)


class _Enum:

    def __init__(self, fields):
        self.fields = fields


class _Array:

    def __init__(self, element_type):
        self.element_type = element_type


class _Maybe:

    def __init__(self, element_type):
        self.element_type = element_type


class _Dict:

    def __init__(self, element_type):
        self.element_type = element_type


class _CustomType:

    def __init__(self, name):
        self.name = name


class _Alias:

    def __init__(self, name, varlink_type):
        self.name = name
        self.type = varlink_type


class _Method:

    def __init__(self, name, in_type, out_type, _signature):
        self.name = name
        self.in_type = in_type
        self.out_type = out_type
        self.signature = _signature


class _Error:

    def __init__(self, name, varlink_type):
        self.name = name
        self.type = varlink_type


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
    Instantiate your own class and set the class variable service to your global varlink.Service object.
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
    """VarlinkServer

    The same as the standard socketserver.TCPServer, to initialize with a subclass of VarlinkRequestHandler.

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
                port = address[p + 1:]
                address = address[:p]
            else:
                raise ConnectionError("Invalid address 'tcp:%s'" % address)
            address = address.replace('[', '')
            address = address.replace(']', '')

            res = socket.getaddrinfo(address, port, proto=socket.IPPROTO_TCP, flags=socket.AI_NUMERICHOST)
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
        self.socket.close()

        if self.remove_file:
            os.remove(self.remove_file)

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
            request.shutdown(socket.SHUT_WR)
        except OSError:
            pass  # some platforms may raise ENOTCONN here
        self.close_request(request)

    def close_request(self, request):
        """Called to clean up an individual request."""
        request.close()


class ThreadingServer(ThreadingMixIn, Server): pass


class ForkingServer(ForkingMixIn, Server): pass
