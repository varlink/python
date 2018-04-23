"""An implementation of the varlink protocol

See http://varlink.org for more information about the varlink protocol and interface definition files.

For service implementations use the Server() class, for client implementations use the Client() class.
"""

__all__ = ['VarlinkEncoder', 'VarlinkError',
           'InterfaceNotFound', 'MethodNotFound', 'MethodNotImplemented', 'InvalidParameter',
           'ClientInterfaceHandler', 'SimpleClientInterfaceHandler', 'Client',
           'Service', 'Interface', 'Scanner', 'ConnectionError',
           'get_listen_fd', 'Server', 'ThreadingServer', 'ForkingServer', 'RequestHandler']

from .client import (Client, ClientInterfaceHandler, SimpleClientInterfaceHandler)
from .error import (VarlinkEncoder, VarlinkError, InvalidParameter, InterfaceNotFound, MethodNotImplemented,
                    MethodNotFound, ConnectionError, BrokenPipeError)
from .scanner import (Scanner, Interface)
from .server import (Service, get_listen_fd, Server, ThreadingServer, ForkingServer, RequestHandler)


# There are no tests here, so don't try to run anything discovered from
# introspecting the symbols (e.g. FunctionTestCase). Instead, all our
# tests come from within varlink.tests.
def load_tests(loader, tests, pattern):
    import os.path
    # top level directory cached on loader instance
    this_dir = os.path.dirname(__file__)
    return loader.discover(start_dir=this_dir, pattern=pattern)
