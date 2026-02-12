"""An implementation of the varlink protocol

See https://www.varlink.org for more information about the varlink protocol and interface definition
files.

For server implementations, create a :class:`varlink.Service`, define your interfaces with the
``@service.interface()`` decorator, wire it to a :class:`varlink.RequestHandler` subclass, and run it
with one of the server classes:

- :class:`varlink.Server` -- single-connection base server (analogous to ``socketserver.TCPServer``)
- :class:`varlink.ThreadingServer` -- multi-threaded server for concurrent connections
- :class:`varlink.ForkingServer` -- multi-process server (Unix/Linux only)

All server classes live in the ``varlink`` package; import them from ``varlink``, not from
``socketserver``.

For client implementations use the :class:`varlink.Client` class.

For installation and examples, see the GIT repository https://github.com/varlink/python
or the `source code <_modules/varlink/tests/test_orgexamplemore.html>`_ of
:mod:`varlink.tests.test_orgexamplemore`

"""

import os

if hasattr(os, "fork"):
    __all__ = [
        "Client",
        "ClientInterfaceHandler",
        "SimpleClientInterfaceHandler",
        "Service",
        "RequestHandler",
        "Server",
        "ThreadingServer",
        "ForkingServer",
        "InterfaceNotFound",
        "MethodNotFound",
        "MethodNotImplemented",
        "InvalidParameter",
        "VarlinkEncoder",
        "VarlinkError",
        "Interface",
        "Scanner",
        "get_listen_fd",
    ]
    from .server import ForkingServer
else:
    __all__ = [
        "Client",
        "ClientInterfaceHandler",
        "SimpleClientInterfaceHandler",
        "Service",
        "RequestHandler",
        "Server",
        "ThreadingServer",
        "InterfaceNotFound",
        "MethodNotFound",
        "MethodNotImplemented",
        "InvalidParameter",
        "VarlinkEncoder",
        "VarlinkError",
        "Interface",
        "Scanner",
        "get_listen_fd",
    ]

from .client import Client, ClientInterfaceHandler, SimpleClientInterfaceHandler
from .error import (
    InterfaceNotFound,
    InvalidParameter,
    MethodNotFound,
    MethodNotImplemented,
    VarlinkEncoder,
    VarlinkError,
)
from .scanner import Interface, Scanner
from .server import RequestHandler, Server, Service, ThreadingServer, get_listen_fd


# There are no tests here, so don't try to run anything discovered from
# introspecting the symbols (e.g. FunctionTestCase). Instead, all our
# tests come from within varlink.tests.
def load_tests(loader, tests, pattern):
    import os.path
    import sys
    from fnmatch import fnmatch

    if pattern is None:
        pattern = "test_*.py"

    # top level directory cached on loader instance
    test_dir = os.path.dirname(__file__) + "/tests"
    for fn in os.listdir(test_dir):
        if fnmatch(fn, pattern):
            modname = "varlink.tests." + fn[:-3]
            __import__(modname)
            module = sys.modules[modname]
            tests.addTest(loader.loadTestsFromModule(module))
    return tests
