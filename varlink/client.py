# coding=utf-8

from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

from builtins import next
from builtins import object
from builtins import open
from builtins import str

from .error import (VarlinkError, InterfaceNotFound, VarlinkEncoder, BrokenPipeError)
from .scanner import (Interface, _Method)

PY2 = sys.version_info[0] == 2
PY3 = (sys.version_info[0] >= 3)

if PY2:
    FileNotFoundError = IOError
    ChildProcessError = OSError

"""
Fix windows Popen for supporting socket as pipe
"""
if sys.platform == "win32":
    import msvcrt

    if sys.version_info < (3, 0):
        import _subprocess
    else:
        import _winapi

    SO_OPENTYPE = 0x7008
    SO_SYNCHRONOUS_NONALERT = 0x20

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    if sys.version_info >= (3, 0):
        DEVNULL = subprocess.DEVNULL

    # Enable socket to be non overlapped
    try:
        dummy = socket.socket(0xDEAD, socket.SOCK_STREAM)  # After that python will not force WSA_FLAG_OVERLAPPED
    except:
        pass
    dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy.setsockopt(socket.SOL_SOCKET, SO_OPENTYPE, SO_SYNCHRONOUS_NONALERT)


    class SocketPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super(SocketPopen, self).__init__(*args, **kwargs)

        if sys.version_info < (3, 0):
            def _get_handles(self, stdin, stdout, stderr):
                """Construct and return tuple with IO objects:
                p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
                """
                to_close = set()
                if stdin is None and stdout is None and stderr is None:
                    return (None, None, None, None, None, None), to_close

                p2cread, p2cwrite = None, None
                c2pread, c2pwrite = None, None
                errread, errwrite = None, None

                if stdin is None:
                    p2cread = _subprocess.GetStdHandle(_subprocess.STD_INPUT_HANDLE)
                    if p2cread is None:
                        p2cread, _ = _subprocess.CreatePipe(None, 0)
                elif stdin == PIPE:
                    p2cread, p2cwrite = _subprocess.CreatePipe(None, 0)
                elif isinstance(stdin, int):
                    p2cread = msvcrt.get_osfhandle(stdin)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        p2cread = msvcrt.get_osfhandle(stdin.fileno())
                    else:
                        p2cread = stdin.fileno()
                p2cread = self._make_inheritable(p2cread)
                # We just duplicated the handle, it has to be closed at the end
                to_close.add(p2cread)
                if stdin == PIPE:
                    to_close.add(p2cwrite)

                if stdout is None:
                    c2pwrite = _subprocess.GetStdHandle(_subprocess.STD_OUTPUT_HANDLE)
                    if c2pwrite is None:
                        _, c2pwrite = _subprocess.CreatePipe(None, 0)
                elif stdout == PIPE:
                    c2pread, c2pwrite = _subprocess.CreatePipe(None, 0)
                elif isinstance(stdout, int):
                    c2pwrite = msvcrt.get_osfhandle(stdout)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        c2pwrite = msvcrt.get_osfhandle(stdout.fileno())
                    else:
                        c2pwrite = stdout.fileno()
                c2pwrite = self._make_inheritable(c2pwrite)
                # We just duplicated the handle, it has to be closed at the end
                to_close.add(c2pwrite)
                if stdout == PIPE:
                    to_close.add(c2pread)

                if stderr is None:
                    errwrite = _subprocess.GetStdHandle(_subprocess.STD_ERROR_HANDLE)
                    if errwrite is None:
                        _, errwrite = _subprocess.CreatePipe(None, 0)
                elif stderr == PIPE:
                    errread, errwrite = _subprocess.CreatePipe(None, 0)
                elif stderr == STDOUT:
                    errwrite = c2pwrite
                elif isinstance(stderr, int):
                    errwrite = msvcrt.get_osfhandle(stderr)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        errwrite = msvcrt.get_osfhandle(stderr.fileno())
                    else:
                        errwrite = stderr.fileno()
                errwrite = self._make_inheritable(errwrite)
                # We just duplicated the handle, it has to be closed at the end
                to_close.add(errwrite)
                if stderr == PIPE:
                    to_close.add(errread)

                return (p2cread, p2cwrite,
                        c2pread, c2pwrite,
                        errread, errwrite), to_close
        else:
            def _get_handles(self, stdin, stdout, stderr):
                """Construct and return tuple with IO objects:
                p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
                """
                if stdin is None and stdout is None and stderr is None:
                    return (-1, -1, -1, -1, -1, -1)

                p2cread, p2cwrite = -1, -1
                c2pread, c2pwrite = -1, -1
                errread, errwrite = -1, -1

                if stdin is None:
                    p2cread = _winapi.GetStdHandle(_winapi.STD_INPUT_HANDLE)
                    if p2cread is None:
                        p2cread, _ = _winapi.CreatePipe(None, 0)
                        p2cread = subprocess.Handle(p2cread)
                        _winapi.CloseHandle(_)
                elif stdin == PIPE:
                    p2cread, p2cwrite = _winapi.CreatePipe(None, 0)
                    p2cread, p2cwrite = subprocess.Handle(p2cread), subprocess.Handle(p2cwrite)
                elif stdin == DEVNULL:
                    p2cread = msvcrt.get_osfhandle(self._get_devnull())
                elif isinstance(stdin, int):
                    p2cread = msvcrt.get_osfhandle(stdin)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        p2cread = msvcrt.get_osfhandle(stdin.fileno())
                    else:
                        p2cread = stdin.fileno()
                p2cread = self._make_inheritable(p2cread)

                if stdout is None:
                    c2pwrite = _winapi.GetStdHandle(_winapi.STD_OUTPUT_HANDLE)
                    if c2pwrite is None:
                        _, c2pwrite = _winapi.CreatePipe(None, 0)
                        c2pwrite = subprocess.Handle(c2pwrite)
                        _winapi.CloseHandle(_)
                elif stdout == PIPE:
                    c2pread, c2pwrite = _winapi.CreatePipe(None, 0)
                    c2pread, c2pwrite = subprocess.Handle(c2pread), subprocess.Handle(c2pwrite)
                elif stdout == DEVNULL:
                    c2pwrite = msvcrt.get_osfhandle(self._get_devnull())
                elif isinstance(stdout, int):
                    c2pwrite = msvcrt.get_osfhandle(stdout)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        c2pwrite = msvcrt.get_osfhandle(stdout.fileno())
                    else:
                        c2pwrite = stdout.fileno()
                c2pwrite = self._make_inheritable(c2pwrite)

                if stderr is None:
                    errwrite = _winapi.GetStdHandle(_winapi.STD_ERROR_HANDLE)
                    if errwrite is None:
                        _, errwrite = _winapi.CreatePipe(None, 0)
                        errwrite = subprocess.Handle(errwrite)
                        _winapi.CloseHandle(_)
                elif stderr == PIPE:
                    errread, errwrite = _winapi.CreatePipe(None, 0)
                    errread, errwrite = subprocess.Handle(errread), subprocess.Handle(errwrite)
                elif stderr == STDOUT:
                    errwrite = c2pwrite
                elif stderr == DEVNULL:
                    errwrite = msvcrt.get_osfhandle(self._get_devnull())
                elif isinstance(stderr, int):
                    errwrite = msvcrt.get_osfhandle(stderr)
                else:
                    # Assuming file-like object
                    if not hasattr(stdin, 'recv'):
                        errwrite = msvcrt.get_osfhandle(stderr.fileno())
                    else:
                        errwrite = stderr.fileno()
                errwrite = self._make_inheritable(errwrite)

                return (p2cread, p2cwrite,
                        c2pread, c2pwrite,
                        errread, errwrite)


    _Popen = SocketPopen
else:
    _Popen = subprocess.Popen


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

        if hasattr(self._connection, 'send_bytes'):
            self._send_bytes = True
            self._sendall = False
        elif hasattr(self._connection, 'sendall'):
            self._send_bytes = False
            self._sendall = True
        else:
            if not hasattr(self._connection, 'write'):
                raise TypeError
            self._sendall = False
            self._send_bytes = False

        if hasattr(self._connection, 'recv_bytes'):
            self._recv_bytes = True
            self._recv = False
        elif hasattr(self._connection, 'recv'):
            self._recv = True
            self._recv_bytes = False
        else:
            if not hasattr(self._connection, 'read'):
                raise TypeError
            self._recv = False
            self._recv_bytes = False

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
        if self._send_bytes:
            self._connection.send_bytes(out + b'\0')
        elif self._sendall:
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
                yield message.decode('utf-8')
                continue

            if self._recv_bytes:
                try:
                    data = self._connection.recv_bytes(8192)
                except:
                    data = []
            elif self._recv:
                try:
                    data = self._connection.recv(8192)
                except:
                    data = []
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
        """Creates a Client object to reach the interfaces of a varlink service.
        For more constructors see the class constructor methods new_with_*() returning an Client object.

        :param address: the exact address like "unix:/run/org.varlink.resolver"
        :param resolve_interface: an interface name, which is resolved with the system wide resolver
        :param resolver: the exact address of the resolver to be used to resolve the interface name
        :exception ConnectionError: could not connect to the service or resolver

        """
        self._interfaces = {}
        self._socket = None
        self._socket_fn = None
        self._tmpdir = None
        self._child_pid = 0
        self._str = "Client<uninitialized>"

        with open(os.path.join(os.path.dirname(__file__), 'org.varlink.service.varlink')) as f:
            interface = Interface(f.read())
            self.add_interface(interface)

        if resolve_interface:
            self._with_interface(resolve_interface, resolver)

        if address:
            self._with_address(address)

    def __enter__(self):
        return self

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __str__(self):
        return self._str

    @classmethod
    def new_with_activate(cls, argv):
        """Creates a Client object to a varlink service server started via socket activation.

        :param argv: executable in argv[0] and parameters in argv[1:] to run the
                     varlink service server via socket activation.

        """
        return cls()._with_activate(argv)

    def _with_activate(self, argv):
        s = socket.socket(socket.AF_UNIX)
        s.setblocking(False)
        self._tmpdir = tempfile.mkdtemp()
        address = self._tmpdir + "/" + str(os.getpid())
        s.bind(address)
        s.listen(100)

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

            for i in range(1, len(argv)):
                argv[i] = argv[i].replace("$VARLINK_ADDRESS", "unix:" + address)

            os.environ["VARLINK_ADDRESS"] = "unix:" + address
            os.environ["LISTEN_FDS"] = "1"
            os.environ["LISTEN_FDNAMES"] = "varlink"
            os.environ["LISTEN_PID"] = str(os.getpid())
            os.execvp(argv[0], argv)
            sys.exit(1)
        # parent
        s.close()

        self._with_address("unix:" + address)

        return self

    @classmethod
    def new_with_bridge(cls, argv):
        """Creates a Client object to a varlink service started via the bridge command.
        The bridge command like "ssh <host> varlink bridge" is executed for every connection.
        This client object will do IO via stdio to the bridge command.

        :param argv: executable in argv[0] and parameters in argv[1:] to run the
                     varlink service server via the bridge connection.

        """
        return cls()._with_bridge(argv)

    def _with_bridge(self, argv):
        def new_bridge_socket():
            sp = socket.socketpair()
            p = _Popen(argv, stdin=sp[1], stdout=sp[1], close_fds=True)

            self._child_pid = p.pid
            return sp[0]

        self._str = "Bridge with: '%s'" % " ".join(argv)
        self._socket_fn = new_bridge_socket
        return self

    @classmethod
    def new_with_address(cls, address):
        """Creates a Client object to reach the interfaces of a varlink service.

        :param address: the exact address like "unix:/run/org.varlink.resolver"
        :exception ConnectionError: could not connect to the service or resolver

        """

        return cls()._with_address(address)

    def _with_address(self, address):
        if address.startswith("unix:"):
            self._str = address
            address = address[5:]
            mode = address.find(';')
            if mode != -1:
                address = address[:mode]
            if address[0] == '@':
                address = address.replace('@', '\0', 1)

            def open_unix():
                s = socket.socket(socket.AF_UNIX)
                s.setblocking(True)
                s.connect(address)
                return s

            self._socket_fn = open_unix

        elif address.startswith("tcp:"):
            self._str = address
            address = address[4:]
            p = address.rfind(':')
            if p != -1:
                port = address[p + 1:]
                address = address[:p]
            else:
                raise ConnectionError("Invalid address 'tcp:%s'" % address)
            address = address.replace('[', '')
            address = address.replace(']', '')

            def open_tcp():
                s = socket.create_connection((address, int(port)))
                s.setblocking(True)
                return s

            self._socket_fn = open_tcp

        elif address is not None:
            raise ConnectionError("Invalid address '%s'" % address)

        return self

    @classmethod
    def new_with_resolved_interface(cls, interface, resolver_address=None):
        """Creates a Client object to reach the interfaces of a varlink service.

        :param interface: an interface name, which is resolved with the system wide resolver
        :param resolver_address: the exact address of the resolver to be used to resolve the interface name
        :exception ConnectionError: could not connect to the service or resolver

        """

        return cls()._with_resolved_interface(interface, resolver_address)

    def _with_resolved_interface(self, interface, resolver_address=None):
        if not resolver_address:
            resolver_address = "unix:/run/org.varlink.resolver"

        if interface == 'org.varlink.resolver':
            self._with_address(resolver_address)
        else:
            with Client.new_with_address(resolver_address) as client, \
                    client.open('org.varlink.resolver') as _rc:
                # noinspection PyUnresolvedReferences
                _r = _rc.Resolve(interface)
                self._with_address(_r['address'])

        return self

    def cleanup(self):
        if hasattr(self, "_tmpdir") and self._tmpdir != None:
            try:
                shutil.rmtree(self._tmpdir)
            except FileNotFoundError:
                pass

        if hasattr(self, "_child_pid") and self._child_pid != 0:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except OSError:
                pass
            try:
                os.waitpid(self._child_pid, 0)
            except ChildProcessError:
                pass

    def open(self, interface_name, namespaced=False, connection=None):
        """Open a new connection and get a client interface handle with the varlink methods installed.

        :param interface_name: an interface name, which the service this client object is
                               connected to, provides.
        :param namespaced: If arguments and return values are instances of SimpleNamespace
                            rather than dictionaries.
        :param connection: If set, get the interface handle for an already opened connection.
        :exception InterfaceNotFound: if the interface is not found

        """

        if not connection:
            connection = self.open_connection()

        if interface_name not in self._interfaces:
            self.get_interface(interface_name, socket_connection=connection)

        if interface_name not in self._interfaces:
            raise InterfaceNotFound(interface_name)

        return self.handler(self._interfaces[interface_name], connection, namespaced=namespaced)

    def open_connection(self):
        """Open a new connection and return the socket.
        :exception OSError: anything socket.connect() throws

        """
        return self._socket_fn()

    def get_interfaces(self, socket_connection=None):
        """Returns the a list of Interface objects the service implements."""
        if not socket_connection:
            socket_connection = self.open_connection()
            close_socket = True
        else:
            close_socket = False

        # noinspection PyUnresolvedReferences
        _service = self.handler(self._interfaces["org.varlink.service"], socket_connection)
        self.info = _service.GetInfo()

        if close_socket:
            socket_connection.close()

        return self.info['interfaces']

    def get_interface(self, interface_name, socket_connection=None):
        if not socket_connection:
            socket_connection = self.open_connection()
            close_socket = True
        else:
            close_socket = False

        _service = self.handler(self._interfaces["org.varlink.service"], socket_connection)
        # noinspection PyUnresolvedReferences
        desc = _service.GetInterfaceDescription(interface_name)
        interface = Interface(desc['description'])
        self._interfaces[interface.name] = interface

        if close_socket:
            socket_connection.close()

        return interface

    def add_interface(self, interface):
        """Manually add or overwrite an interface definition from an Interface object.

        :param interface: an Interface() object

        """
        if not isinstance(interface, Interface):
            raise TypeError

        self._interfaces[interface.name] = interface
