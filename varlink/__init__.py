#!/usr/bin/python3

import collections
import json
import re
import select
import socket
import traceback

class Scanner:
    def __init__(self, string):
        self.whitespace = re.compile(r'([ \t\n]|#.*$)+', re.ASCII | re.MULTILINE)

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


class Int:
    pass

class String:
    pass

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
    def __init__(self, name, in_type, out_type):
        self.name = name
        self.in_type = in_type
        self.out_type = out_type

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

    def get_method(self, name):
        method = self.members.get(name)
        if method and type(method) == Method:
            return method


def read_type(scanner):
    if scanner.get('bool'):
        t = String()
    elif scanner.get('int'):
        t = String()
    elif scanner.get('float'):
        t = String()
    elif scanner.get('string'):
        t = String()
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
        in_type = read_struct(scanner)
        scanner.expect('->')
        out_type = read_struct(scanner)
        return Method(name, in_type, out_type)
    elif scanner.get('error'):
        return Error(scanner.expect('member-name'), read_type(scanner))
    else:
        raise SyntaxError('expected type, method, or error')


class Connection:
    def __init__(self, socket):
        self.socket = socket
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
    def __init__(self, name, **parameters):
        self.name = name
        self.parameters = parameters

    def json(self):
        return {
            'error': self.name,
            'parameters': self.parameters
        }

class InterfaceNotFound(VarlinkError):
    def __init__(self, interface):
        self.name = 'org.varlink.service.InterfaceNotFound'
        self.parameters = {
            'interface': interface
        }

class MethodNotFound(VarlinkError):
    def __init__(self, method):
        self.name = 'org.varlink.service.MethodNotFound'
        self.parameters = {
            'method': method
        }

class MethodNotImplemented(VarlinkError):
    def __init__(self, method):
        self.name = 'org.varlink.service.MethodNotImplemented'
        self.parameters = {
            'method': method
        }

class InvalidParameter(VarlinkError):
    def __init__(self, name):
        self.name = 'org.varlink.service.InvalidParameter'
        self.parameters = {
            'parameter': name
        }

class Service:
    def __init__(self, address, vendor, product, version):
        self.address = address
        self.vendor = vendor
        self.product = product
        self.version = version
        self.url = None
        self.interfaces = {}
        self.connections = {}

        self.add_interface('org.varlink.service.varlink', self)

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
            raise InterfaceNotFound(interface_name)

        return { 'description': i.description }

    def serve(self):
        s = socket.socket(socket.AF_UNIX)
        s.setblocking(0)

        address = self.address
        if address[0] == '@':
            address = address.replace('@', '\0', 1)
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
                            reply = { 'error': 'InternalError' }

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

        method = interface.get_method(method_name)
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
        return { 'parameters': out or {} }

    def add_interface(self, filename, handler):
        with open(filename) as f:
            interface = Interface(f.read())
            interface.handler = handler
            self.interfaces[interface.name] = interface

    def interface(self, filename):
        def decorator(interface_class):
            self.add_interface(filename, interface_class())
            return interface_class

        return decorator
