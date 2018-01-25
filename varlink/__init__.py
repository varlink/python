#!/usr/bin/python3

import collections
import json
import os
import sys
import re
import select
import socket
import traceback
from types import SimpleNamespace as Namespace

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

class Struct:
    def __init__(self, fields):
        self.fields = collections.OrderedDict(fields)

class Array:
    def __init__(self, element_type):
        self.element_type = element_type

class CustomType:
    def __init__(self, name):
        self.name = name

class Alias:
    def __init__(self, name, varlink_type):
        self.name = name
        self.type = varlink_type

class Method:
    def __init__(self, name, in_type, out_type, signature):
        self.name = name
        self.in_type = in_type
        self.out_type = out_type
        self.signature = signature

class Error:
    def __init__(self, name, varlink_type):
        self.name = name
        self.type = varlink_type

class Interface:
    def __init__(self, description):
        self.description = description

        scanner = Scanner(description)
        scanner.expect('interface')
        self.name = scanner.expect('interface-name')
        self.members = collections.OrderedDict()
        while not scanner.end():
            member = read_member(scanner)
            self.members[member.name] = member
            if isinstance(member, Method):
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
        method = self._get_method(method_name)
        if not method:
            raise MethodNotFound(method_name)

        sparam = self._filter_params(method.in_type, args, kwargs)
        send = {'method' : self.name + "." + method_name, 'parameters' : sparam}
        return self.handler.send(send).__next__()

    def _call_more(self, method_name, *args, **kwargs):
        method = self._get_method(method_name)
        if not method:
            raise MethodNotFound(method_name)

        sparam = self._filter_params(method.in_type, args, kwargs)
        send = {'method' : self.name + "." + method_name, 'more' : True, 'parameters' : sparam}
        return self.handler.send(send)

    def _get_method(self, name):
        method = self.members.get(name)
        if method and isinstance(method, Method):
            return method

    def _filter_params(self, types, args, kwargs):
        if isinstance(types, CustomType):
            types = self.members.get(types.name)

        if isinstance(types, Alias):
            types = types.type

        if isinstance(types, Array):
            return [self._filter_params(types.element_type, x, None) for x in args]

        if not isinstance(types, Struct):
            return args

        out = {}

        mystruct = None
        if not isinstance(args, tuple):
            mystruct = args
            args = None

        for name in types.fields:
            if isinstance(args, tuple):
                if args:
                    val = args[0]
                    if len(args) > 1:
                        args = args[1:]
                    else:
                        args = None
                    out[name] = self._filter_params(types.fields[name], val, None)
                    continue
                else:
                    if name in kwargs:
                        out[name] = self._filter_params(types.fields[name], kwargs[name], None)
                        continue

            if mystruct:
                try:
                    if isinstance(mystruct, dict):
                        val = mystruct[name]
                    else:
                        val = getattr(mystruct, name)
                    out[name] = self._filter_params(types.fields[name], val, None)
                except:
                    pass

        return out

def read_type(scanner):
    if scanner.get('bool'):
        t = bool()
    elif scanner.get('int'):
        t = int()
    elif scanner.get('float'):
        t = float()
    elif scanner.get('string'):
        t = str()
    else:
        name = scanner.get('member-name')
        if name:
            t = CustomType(name)
        else:
            t = read_struct(scanner)

    if scanner.get('[]'):
        t = Array(t)

    return t

def read_struct(scanner):
    scanner.expect('(')
    fields = collections.OrderedDict()
    if not scanner.get(')'):
        while True:
            name = scanner.expect('identifier')
            scanner.expect(':')
            fields[name] = read_type(scanner)
            if not scanner.get(','):
                break
        scanner.expect(')')

    return Struct(fields)

def read_member(scanner):
    if scanner.get('type'):
        return Alias(scanner.expect('member-name'), read_type(scanner))
    elif scanner.get('method'):
        name = scanner.expect('member-name')
        # FIXME
        sig = scanner.method_signature.match(scanner.string, scanner.pos)
        if sig:
            sig = name + sig.group(0)
        in_type = read_struct(scanner)
        scanner.expect('->')
        out_type = read_struct(scanner)
        return Method(name, in_type, out_type, sig)
    elif scanner.get('error'):
        return Error(scanner.expect('member-name'), read_type(scanner))
    else:
        raise SyntaxError('expected type, method, or error')


class Connection:
    def __init__(self, _socket):
        self.socket = _socket
        self.in_buffer = b''
        self.out_buffer = b''

    def events(self):
        events = 0
        if len(self.in_buffer) < 8 * 1024 * 1024:
            events |= select.EPOLLIN
        if self.out_buffer:
            events |= select.EPOLLOUT
        return events

    def dispatch(self, events):
        if events & select.EPOLLIN:
            data = self.socket.recv(8192)
            if len(data) == 0:
                raise ConnectionError
            self.in_buffer += data
        elif events & select.EPOLLOUT:
            n = self.socket.send(self.out_buffer[:8192])
            self.out_buffer = self.out_buffer[n:]

    def read(self):
        while True:
            message, _, self.in_buffer = self.in_buffer.rpartition(b'\0')
            if message:
                yield json.loads(message)
            else:
                break

    def write(self, message):
        self.out_buffer += json.dumps(message).encode('utf-8')
        self.out_buffer += b'\0'

class VarlinkError(Exception):
    def __init__(self, error, parameters):
        super().__init__({"error" : error, "parameters" : parameters})
        self.error = error
        if isinstance(parameters, dict):
            self.parameters = Namespace(**parameters)
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

class Client(dict):
    def __init__(self, address=None, interface=None, resolver=None):
        dict.__init__(self)

        def _resolve_interface(interface, resolver):
            _iface = Client(resolver)['org.varlink.resolver']
            _r = _iface.Resolve(interface)
            return _r.address

        directory = os.path.dirname(__file__)
        self.add_interface(os.path.join(directory, 'org.varlink.service.varlink'), self)

        if address is None and not (interface is None):
            address = _resolve_interface(interface, resolver or "unix:/run/org.varlink.resolver")

        if address.startswith("unix:"):
            address = address[5:]
            mode = address.rfind(';mode=')
            if mode != -1:
                address = address[:mode]
            if address[0] == '@':
                address = address.replace('@', '\0', 1)

            s = socket.socket(socket.AF_UNIX)
        else:
            # FIXME: also accept other transports
            raise ConnectionError

        s.connect(address)
        self.socket = s
        #self.socket.setblocking(0)
        self.in_buffer = b''
        info = self["org.varlink.service"].GetInfo()
        for iface in info.interfaces:
            desc = self["org.varlink.service"].GetInterfaceDescription(iface)
            interface = Interface(desc.description)
            interface.handler = self
            self[interface.name] = interface

    def recv(self):
        epoll = select.epoll()
        epoll.register(self.socket, select.EPOLLIN)
        while True:
            for fd, events in epoll.poll():
                if not (events & select.EPOLLIN):
                    continue

                data = self.socket.recv(8192)
                if len(data) == 0:
                    raise StopIteration
                    continue

                self.in_buffer += data
                message, _, self.in_buffer = self.in_buffer.rpartition(b'\0')
                if message:
                    yield message
                else:
                    continue
            
    def send(self, out):
        out_buffer = json.dumps(out).encode('utf-8')
        out_buffer += b'\0'
        # FIXME: send until all sent
        self.socket.send(out_buffer)
        for message in self.recv():
            ret = json.loads(message, object_hook=lambda d: Namespace(**d))
            if hasattr(ret, "error"):
                # FIXME: error handling
                raise VarlinkError(ret.error, hasattr(ret, "parameters") and ret.parameters or None)
            else:
                if hasattr(ret, "continues"):
                    continues = ret.continues
                else:
                    continues = False

                yield ret.parameters

                if (continues != True):
                    raise StopIteration

        raise ConnectionError

    def add_interface(self, filename, handler):
        if not os.path.isabs(filename):
            filename = os.path.join(self.interface_dir, filename + '.varlink')

        with open(filename) as f:
            interface = Interface(f.read())
            interface.handler = handler
            self[interface.name] = interface

class Service:
    def __init__(self, vendor='', product='', version='', interface_dir='.'):
        self.vendor = vendor
        self.product = product
        self.version = version
        self.url = None
        self.interfaces = {}
        self.connections = {}
        self.interface_dir = interface_dir

        directory = os.path.dirname(__file__)
        self.add_interface(os.path.join(directory, 'org.varlink.service.varlink'), self)

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

        return {'description': i.description}

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
                    connection = Connection(sock)
                    self.connections[sock.fileno()] = connection
                    epoll.register(sock.fileno(), select.EPOLLIN)
                else:
                    connection = self.connections.get(fd)
                    try:
                        connection.dispatch(events)
                    except ConnectionError:
                        connection.socket.close()
                        continue

                    for message in connection.read():
                        try:
                            reply = self._handle(connection, message)
                        except VarlinkError as error:
                            reply = error.json()
                        except Exception as error:
                            traceback.print_exception(type(error), error, error.__traceback__)
                            reply = {'error': 'InternalError'}

                        connection.write(reply)

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

        method = interface._get_method(method_name)
        if not method:
            raise MethodNotFound(method_name)

        parameters = message.get('parameters', {})
        for name in parameters:
            if name not in method.in_type.fields:
                raise InvalidParameter(name)

        func = getattr(interface.handler, method_name, None)
        if not func or not callable(func):
            raise MethodNotImplemented(method_name)

        out = func(**parameters)
        return {'parameters': out or {}}

    def add_interface(self, filename, handler):
        if not os.path.isabs(filename):
            filename = os.path.join(self.interface_dir, filename + '.varlink')

        with open(filename) as f:
            interface = Interface(f.read())
            interface.handler = handler
            self.interfaces[interface.name] = interface

    def interface(self, filename):
        def decorator(interface_class):
            self.add_interface(filename, interface_class())
            return interface_class

        return decorator
