from __future__ import print_function
from __future__ import unicode_literals

import json

try:
     from types import SimpleNamespace
     ConnectionError = ConnectionError
     BrokenPipeError = BrokenPipeError
except: # Python 2
     from argparse import Namespace as SimpleNamespace
     class ConnectionError(OSError):
         pass
     class BrokenPipeError(ConnectionError):
         pass

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
        Exception.__init__(self, json.loads(json.dumps(message, cls=VarlinkEncoder)))

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
