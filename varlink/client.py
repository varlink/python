# coding=utf-8

from __future__ import print_function
from __future__ import unicode_literals

from builtins import next
from builtins import open
from builtins import str
from builtins import object

import json
import os
import signal
import socket
import sys

from .error import (VarlinkError, InterfaceNotFound, VarlinkEncoder, BrokenPipeError)
from .scanner import (Interface, _Method)


class ConnectionError(OSError):
    pass


class ClientInterfaceHandler(object):
    """Base class for varlink client, which wraps varlink methods of an interface to the class"""

    def __init__(self, interface, namespaced=False):
        """Base class for varlink client, which wraps varlink methods of an interface.

        The object allows to talk to a varlink service, which implements the specified interface
        transparently by calling the methods. The call blocks until enough messages are received.

        For monitor calls with '_more=True' a generator object is returned.

        :param interface: an Interface object
        :param namespaced: if True, varlink methods return SimpleNamespace objects instead of dictionaries

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

        if sys.version_info.major >= 3:
            _wrapped.__name__ = method.name
        else:
            _wrapped.__name__ = method.name.encode("latin-1")

        # FIXME: add comments
        if method.signature:
            if method.doc:
                _wrapped.__doc__ = method.doc + "\n"
            else:
                _wrapped.__doc__ = ""
                "\n"
            _wrapped.__doc__ += method.signature
        setattr(self, method.name, _wrapped)

    def _next_varlink_message(self):
        message = next(self._next_message())

        message = json.loads(message)
        if not 'parameters' in message:
            message['parameters'] = {}

        if 'error' in message and message["error"] != None:
            self._in_use = False
            e = VarlinkError.new(message, self._namespaced)
            raise e
        else:
            return message['parameters'], ('continues' in message) and message['continues']

    def _call(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError("Tried to call a varlink method, while other call still in progress")

        oneway = False
        if "_oneway" in kwargs and kwargs.pop("_oneway"):
            oneway = True

        method = self._interface.get_method(method_name)

        parameters = self._interface.filter_params("client.call", method.in_type, False, args, kwargs)

        out = {'method': self._interface.name + "." + method_name}

        if oneway:
            out['oneway'] = True

        if parameters:
            out['parameters'] = parameters

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
            message = self._interface.filter_params("client.reply", method.out_type, self._namespaced, message, None)

        return message

    def _call_more(self, method_name, *args, **kwargs):
        if self._in_use:
            raise ConnectionError("Tried to call a varlink method, while other call still in progress")

        method = self._interface.get_method(method_name)

        parameters = self._interface.filter_params("client.call", method.in_type, False, args, kwargs)
        out = {'method': self._interface.name + "." + method_name, 'more': True, 'parameters': parameters}

        self._send_message(json.dumps(out, cls=VarlinkEncoder).encode('utf-8'))

        more = True
        self._in_use = True
        while more:
            (message, more) = self._next_varlink_message()
            if message:
                message = self._interface.filter_params("client.reply", method.out_type, self._namespaced, message,
                                                        None)
            yield message
        self._in_use = False


class SimpleClientInterfaceHandler(ClientInterfaceHandler):
    """A varlink client for an interface doing send/write and receive/read on a socket or file stream"""

    def __init__(self, interface, file_or_socket, namespaced=False):
        """Creates an object with the varlink methods of an interface installed.

        The object allows to talk to a varlink service, which implements the specified interface
        transparently by calling the methods. The call blocks until enough messages are received.

        For monitor calls with '_more=True' a generator object is returned.

        :param interface: an Interface object
        :param file_or_socket: an open socket or io stream
        :param namespaced: if True, varlink methods return SimpleNamespace objects instead of dictionaries
        
        """
        ClientInterfaceHandler.__init__(self, interface, namespaced=namespaced)
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
        except:
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


class Client(object):
    """Varlink client class.

        >>> with varlink.Client("unix:/run/org.example.ping") as client, client.open('org.example.ping') as connection:
        >>>     assert connection.Ping("Test")["pong"] == "Test"

    If the varlink resolver is running:

        >>> client = varlink.Client(resolve_interface='com.redhat.logging')
        >>> print(client.get_interfaces()['com.redhat.logging'].get_description())
        # Query and monitor the log messages of a system.
        interface com.redhat.logging
        type Entry (cursor: string, time: string, message: string, process: string, priority: string)
        # Monitor the log. Returns the @initial_lines most recent entries in the
        # first reply and then continuously replies when new entries are available.
        method Monitor(initial_lines: int) -> (entries: Entry[])
        >>> connection = client.open("com.redhat.logging")

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

        :param address: the exact address like "unix:/run/org.varlink.resolver"
        :param resolve_interface: an interface name, which is resolved with the system wide resolver
        :param resolver: the exact address of the resolver to be used to resolve the interface name
        :exception ConnectionError: could not connect to the service or resolver

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
        self.info = _connection.GetInfo()

        for interface_name in self.info['interfaces']:
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

        :param interface_name: an interface name, which the service this client object is
                               connected to, provides.
        :param namespaced: If arguments and return values are instances of SimpleNamespace
                            rather than dictionaries.
        :exception InterfaceNotFound: if the interface is not found
        :exception OSError: anything socket.connect() throws

        """

        if interface_name not in self._interfaces:
            raise InterfaceNotFound(interface_name)

        if self.port:
            s = socket.create_connection((self.address, int(self.port)))
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

        :param interface: an Interface() object

        """
        if not isinstance(interface, Interface):
            raise TypeError

        self._interfaces[interface.name] = interface
