#!/usr/bin/python3

"""An implementation of the varlink protocol

See http://varlink.org for more information about the varlink protocol and interface definition files.

For service implementations use the Server() class, for client implementations use the Client() class.
"""

import collections
import json
import os
import re
import select
import socket
import traceback
from types import (SimpleNamespace, GeneratorType)
from inspect import signature

class Scanner:
    def __init__(self, string):
        self.whitespace = re.compile(r'([ \t\n]|#.*$)+', re.ASCII | re.MULTILINE)
        # FIXME: nested ()
        self.method_signature = re.compile(r'([ \t\n]|#.*$)*(\([^)]*\))([ \t\n]|#.*$)*->([ \t\n]|#.*$)*(\([^)]*\))', re.ASCII | re.MULTILINE)

        self.keyword_pattern = re.compile(r'\b[a-z]+\b|[:,(){}]|->|\[\]', re.ASCII)
        self.patterns = {
            'interface-name': re.compile(r'[a-z]+(\.[a-z0-9][a-z0-9-]*)+'),
            'member-name': re.compile(r'\b[A-Z][A-Za-z0-9_]*\b', re.ASCII),
            'identifier': re.compile(r'\b[A-Za-z0-9_]+\b', re.ASCII),
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
            raise SyntaxError('expected {}'.format(expected))
        return value

    def end(self):
        m = self.whitespace.match(self.string, self.pos)
        if m:
            self.pos = m.end()

        return self.pos >= len(self.string)

    def read_type(self):
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

        if self.get('[]'):
            t = _Array(t)

        return t

    def read_struct(self):
        self.expect('(')
        fields = collections.OrderedDict()
        if not self.get(')'):
            while True:
                name = self.expect('identifier')
                self.expect(':')
                fields[name] = self.read_type()
                if not self.get(','):
                    break
            self.expect(')')

        return _Struct(fields)

    def read_member(self):
        if self.get('type'):
            return _Alias(self.expect('member-name'), self.read_type())
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

class _Struct:
    def __init__(self, fields):
        self.fields = collections.OrderedDict(fields)

class _Array:
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
    def __init__(self, name, in_type, out_type, signature):
        self.name = name
        self.in_type = in_type
        self.out_type = out_type
        self.signature = signature

class _Error:
    def __init__(self, name, varlink_type):
        self.name = name
        self.type = varlink_type

class _ClientInterfaceHandler:
    def __init__(self, interface, connection):
        self._interface = interface
        self._connection = connection
        self._in_use = False

        for member in interface._members.values():
            if isinstance(member, _Method):
                self._add_method(member)

    def _add_method(self, method):
        def _wrapped(*args, **kwds):
            if "_more" in kwds and kwds.pop("_more"):
                return self._call_more(method.name, *args, **kwds)
            else:
                return self._call(method.name, *args, **kwds)
        _wrapped.__name__ = method.name
        # FIXME: add comments
        _wrapped.__doc__ = "Varlink call: " + method.signature
        setattr(self, method.name, _wrapped)

    def _call(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError

        method = self._interface.get_method(method_name)

        sparam = self._interface.filter_params(method.in_type, args, kwargs)
        send = {'method' : self._interface._name + "." + method_name, 'parameters' : sparam}
        try:
            self._in_use = True
            (ret, more) = next(self._connection.send_and_recv(send))
            if more:
                self._connection.close()
                self._in_use = False
                raise ConnectionError
            self._in_use = False
            return ret
        except StopIteration:
            pass

        self._in_use = False
        raise ConnectionError

    def _call_more(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError
        method = self._interface.get_method(method_name)

        sparam = self._interface.filter_params(method.in_type, args, kwargs)
        send = {'method' : self._interface._name + "." + method_name, 'more' : True, 'parameters' : sparam}
        more = True
        self._in_use = True
        for (ret, more) in self._connection.send_and_recv(send):
            yield ret
            if not more:
                break
        self._in_use = False

class Interface:
    """Class for a parsed varlink interface definition."""
    def __init__(self, description):
        """description -- description string in varlink interface definition language"""
        self._description = description

        scanner = Scanner(description)
        scanner.expect('interface')
        self._name = scanner.expect('interface-name')
        self._members = collections.OrderedDict()
        while not scanner.end():
            member = scanner.read_member()
            self._members[member.name] = member

    def get_description(self):
        """return the description string in varlink interface definition language"""
        return self._description

    def get_method(self, name):
        method = self._members.get(name)
        if method and isinstance(method, _Method):
            return method
        raise MethodNotFound(name)

    def filter_params(self, vtype, args, kwargs):
        if isinstance(vtype, _CustomType):
            return self.filter_params(self._members.get(vtype.name), args, kwargs)

        if isinstance(vtype, _Alias):
            return self.filter_params(self._members.get(vtype.type), args, kwargs)

        if isinstance(vtype, _Array):
            return [self.filter_params(vtype.element_type, x, None) for x in args]

        if not isinstance(vtype, _Struct):
            return args

        out = {}

        mystruct = None
        if not isinstance(args, tuple):
            mystruct = args
            args = None

        for name in vtype.fields:
            if isinstance(args, tuple):
                if args:
                    val = args[0]
                    if len(args) > 1:
                        args = args[1:]
                    else:
                        args = None
                    out[name] = self.filter_params(vtype.fields[name], val, None)
                    continue
                else:
                    if name in kwargs:
                        out[name] = self.filter_params(vtype.fields[name], kwargs[name], None)
                        continue

            if mystruct:
                try:
                    if isinstance(mystruct, dict):
                        val = mystruct[name]
                    else:
                        val = getattr(mystruct, name)
                    out[name] = self.filter_params(vtype.fields[name], val, None)
                except:
                    pass

        return out

class _Connection:
    def __init__(self, _socket):
        self._socket = _socket
        self._in_buffer = b''
        self._out_buffer = b''

    def close(self):
        self._socket.close()

    def events(self):
        events = 0
        if len(self._in_buffer) < (32 * 1024 * 1024):
            events |= select.EPOLLIN
        if self._out_buffer:
            events |= select.EPOLLOUT
        return events

    def dispatch(self, events):
        if events & select.EPOLLOUT:
            n = self._socket.send(self._out_buffer[:8192])
            self._out_buffer = self._out_buffer[n:]

        if events & select.EPOLLIN:
            data = self._socket.recv(8192)
            if len(data) == 0:
                raise ConnectionError
            self._in_buffer += data

    def read(self):
        while True:
            message, _, self._in_buffer = self._in_buffer.partition(b'\0')
            if message:
                yield json.loads(message)
            else:
                break

    def write(self, message):
        self._out_buffer += json.dumps(message).encode('utf-8')
        self._out_buffer += b'\0'

    def read_namespace(self):
        while True:
            message, _, self._in_buffer = self._in_buffer.partition(b'\0')
            if message:
                yield json.loads(message, object_hook=lambda d: SimpleNamespace(**d))
            else:
                break

    def send_and_recv(self, out):
        self.write(out)
        epoll = select.epoll()
        epoll.register(self._socket.fileno(), select.EPOLLOUT | select.EPOLLIN)
        while True:
            for fd, events in epoll.poll():
                try:
                    self.dispatch(events)
                except ConnectionError:
                    self._socket.close()
                    return

                for message in self.read_namespace():
                    if hasattr(message, "error"):
                        # FIXME: error handling
                        raise VarlinkError(message.error, hasattr(message, "parameters") and message.parameters or None)

                    yield (message.parameters, hasattr(message, "continues") and getattr(message, "continues"))

                ev = self.events()
                epoll.modify(fd, ev)

class ConnectionError(Exception):
    def __init__(self):
        super().__init__()

class VarlinkError(Exception):
    def __init__(self, error, parameters):
        super().__init__({"error" : error, "parameters" : parameters})
        self.error = error
        if isinstance(parameters, dict):
            self.parameters = SimpleNamespace(**parameters)
        else:
            self.parameters = parameters

    def json(self):
        return self.args[0]

class InterfaceNotFound(VarlinkError):
    def __init__(self, interface):
        VarlinkError.__init__(self, 'org.varlink.service.InterfaceNotFound', {'interface': interface})

class MethodNotFound(VarlinkError):
    def __init__(self, method):
        VarlinkError.__init__(self, 'org.varlink.service.MethodNotFound', {'method': method})

class MethodNotImplemented(VarlinkError):
    def __init__(self, method):
        VarlinkError.__init__(self, 'org.varlink.service.MethodNotImplemented', {'method': method})

class InvalidParameter(VarlinkError):
    def __init__(self, name):
        VarlinkError.__init__(self, 'org.varlink.service.InvalidParameter', {'parameter': name})

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
    >>> iface = client.open("io.systemd.journal")

    iface now holds an object with all the varlink methods available.

    Do varlink method call with varlink arguments and a
    single varlink return struct wrapped in a namespace class:
    >>> ret = iface.Monitor(initial_lines=1)
    >>> ret
    namespace(entries=[namespace(cursor='s=[…]',
       message="req:1 'dhcp4-change' [wlp3s0][…]", priority='critical',
       process='nm-dispatcher', time='2018-01-29 12:19:59Z')])
    >>> ret.entries[0].process
    'nm-dispatcher'

    Do varlink method call with varlink arguments and a
    multiple return values in monitor mode, using the "_more" keyword:
    >>> for m in iface.Monitor(_more=True):
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

        def _resolve_interface(interface, resolver):
            _iface = Client(resolver).open('org.varlink.resolver')
            _r = _iface.Resolve(interface)
            return _r.address

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
            s.setblocking(0)
            s.bind("")
            s.listen()
            address = s.getsockname().decode('ascii')

            pid = os.fork()
            if pid == 0:
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
                address = "unix:%s;mode=0600" % address
                os.execlp(executable, executable, address)
            # parent
            s.close()
        else:
            # FIXME: also accept other transports
            raise ConnectionError

        self.address = address
        siface = self.open("org.varlink.service")
        info = siface.GetInfo()

        for iface in info.interfaces:
            desc = siface.GetInterfaceDescription(iface)
            interface = Interface(desc.description)
            self._interfaces[interface._name] = interface

    def open(self, interface_name):
        """Open a new connection and get a client interface handle with the varlink methods installed.

        Arguments:
        interface_name -- an interface name, which the service this client object is
                          connected to, provides.

        Exceptions:
        InterfaceNotFound -- if the interface is not found
        ConnectionError   -- could not connect to the service
        """

        if not interface_name in self._interfaces:
            raise InterfaceNotFound(interface_name)

        try:
            s = socket.socket(socket.AF_UNIX)
            s.setblocking(0)
            s.connect(self.address)
        except:
            raise ConnectionError

        return _ClientInterfaceHandler(self._interfaces[interface_name], _Connection(s))

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

        self._interfaces[interface._name] = interface

class SimpleService:
    def __init__(self, vendor='', product='', version='', interface_dir='.'):
        self.vendor = vendor
        self.product = product
        self.version = version
        self.url = None
        self.interfaces = {}
        self.connections = {}
        self._more = {}
        self.interface_dir = interface_dir

        directory = os.path.dirname(__file__)
        self._add_interface(os.path.join(directory, 'org.varlink.service.varlink'), self)

    def GetInfo(self):
        return {
            'vendor': self.vendor,
            'product': self.product,
            'version': self.version,
            'url': self.url,
            'interfaces': list(self.interfaces.keys())
        }

    def GetInterfaceDescription(self, interface):
        try:
            i = self.interfaces[interface]
        except KeyError:
            raise InterfaceNotFound(interface)

        return {'description': i._description}

    def serve(self, address, listen_fd=None):
        if listen_fd:
            s = socket.fromfd(listen_fd, socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            if address[0] == '@':
                address = address.replace('@', '\0', 1)

            s = socket.socket(socket.AF_UNIX)
            s.setblocking(0)
            s.bind(address)
            s.listen()

        epoll = select.epoll()
        epoll.register(s, select.EPOLLIN)

        while True:
            for fd, events in epoll.poll():
                if fd == s.fileno():
                    sock, _ = s.accept()
                    sock.setblocking(0)
                    connection = _Connection(sock)
                    self.connections[sock.fileno()] = connection
                    epoll.register(sock.fileno(), select.EPOLLIN)
                else:
                    connection = self.connections.get(fd)
                    try:
                        connection.dispatch(events)
                    except Exception as e:
                        connection.close()
                        if fd in self._more:
                            try:
                                self._more[fd].throw(ConnectionError())
                            except StopIteration:
                                pass
                            del self._more[fd]
                        continue

                    if not fd in self._more:
                        for message in connection.read():
                            try:
                                it = iter(self._handle(connection, message))
                                self._more[fd] = it
                                break
                            except VarlinkError as error:
                                reply = error.json()
                                connection.write(reply)
                            except Exception as error:
                                traceback.print_exception(type(error), error, error.__traceback__)
                                reply = {'error': 'InternalError'}
                                connection.write(reply)

                    if fd in self._more:
                        try:
                            reply = next(self._more[fd])
                            if reply != None:
                                connection.write(reply)
                        except VarlinkError as error:
                            reply = error.json()
                            connection.write(reply)
                            del self._more[fd]
                        except StopIteration:
                            del self._more[fd]
                        except Exception as error:
                            traceback.print_exception(type(error), error, error.__traceback__)
                            reply = {'error': 'InternalError'}
                            connection.write(reply)
                            del self._more[fd]

                    epoll.modify(fd, connection.events())

        s.close()
        epoll.close()

    def _handle(self, connection, message):
        interface_name, _, method_name = message.get('method', '').rpartition('.')
        if not interface_name or not method_name:
            raise InterfaceNotFound(interface_name)

        interface = self.interfaces.get(interface_name)
        if not interface:
            raise InterfaceNotFound(interface_name)

        method = interface.get_method(method_name)

        parameters = message.get('parameters', {})
        for name in parameters:
            if name not in method.in_type.fields:
                raise InvalidParameter(name)

        func = getattr(interface._handler, method_name, None)
        if not func or not callable(func):
            raise MethodNotImplemented(method_name)

        kwargs = {}
        if message.get('more', False) or message.get('oneway', False) or message.get('upgrade', False):
            sig = signature(func)
            if message.get('more', False) and '_more' in sig.parameters:
                kwargs["_more"] = True

            if message.get('oneway', False) and '_oneway' in sig.parameters:
                kwargs["_oneway"] = True

            if message.get('upgrade', False) and '_upgrade' in sig.parameters:
                kwargs["_upgrade"] = True

        out = func(**parameters, **kwargs)

        if isinstance(out, GeneratorType):
            try:
                for o in out:
                    if isinstance(o, Exception):
                        raise o

                    if kwargs.get("_oneway", False):
                        return

                    cont = True
                    if '_continues' in o:
                        cont = o['_continues']
                        del o['_continues']
                        yield { 'continues': bool(cont), 'parameters': o or {}}
                    else:
                        yield { 'parameters': o or {}}

                    if not cont:
                        return
            except ConnectionError as e:
                out.throw(e)
        else:
            yield {'parameters': out or {}}

    def _add_interface(self, filename, handler):
        if not os.path.isabs(filename):
            filename = os.path.join(self.interface_dir, filename + '.varlink')

        with open(filename) as f:
            interface = Interface(f.read())
            interface._handler = handler
            self.interfaces[interface._name] = interface

    def interface(self, filename):
        def decorator(interface_class):
            self._add_interface(filename, interface_class())
            return interface_class

        return decorator
