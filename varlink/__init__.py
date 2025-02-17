"""An implementation of the varlink protocol

See https://www.varlink.org for more information about the varlink protocol and interface definition
files.

For server implementations use the :class:`varlink.Server` class.

For client implementations use the :class:`varlink.Client` class.

For installation and examples, see the GIT repository https://github.com/varlink/python.
or the `source code <_modules/varlink/tests/test_orgexamplemore.html>`_ of
:mod:`varlink.tests.test_orgexamplemore`

"""

import os

if hasattr(os, "fork"):
    __all__ = ['Client', 'ClientInterfaceHandler', 'SimpleClientInterfaceHandler',
               'Service', 'RequestHandler', 'Server', 'ThreadingServer', 'ForkingServer',
               'InterfaceNotFound', 'MethodNotFound', 'MethodNotImplemented', 'InvalidParameter',
               'VarlinkEncoder', 'VarlinkError',
               'Interface', 'Scanner', 'get_listen_fd']
    from .server import ForkingServer
else:
    __all__ = ['Client', 'ClientInterfaceHandler', 'SimpleClientInterfaceHandler',
               'Service', 'RequestHandler', 'Server', 'ThreadingServer',
               'InterfaceNotFound', 'MethodNotFound', 'MethodNotImplemented', 'InvalidParameter',
               'VarlinkEncoder', 'VarlinkError',
               'Interface', 'Scanner', 'get_listen_fd']

from .client import (Client, ClientInterfaceHandler, SimpleClientInterfaceHandler)
from .error import (VarlinkEncoder, VarlinkError, InvalidParameter, InterfaceNotFound, MethodNotImplemented,
                    MethodNotFound)
from .scanner import (Scanner, Interface)
from .server import (Service, get_listen_fd, Server, ThreadingServer, RequestHandler)


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
