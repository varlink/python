from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

from builtins import range
from builtins import str
from builtins import object
from future import standard_library
standard_library.install_aliases()
import getopt
import json
import math
import os
import socket
import sys
import threading
import unittest
from sys import platform

import varlink

######## CLIENT #############

def run_client(address):
    print('Connecting to %s' % address)
    with varlink.Client(address) as client, \
            client.open('org.varlink.certification') as con:
        con.Start(_oneway=True)
        ret = con.Test01()
        print("Test01:", ret)
        ret = con.Test02(ret["bool"])
        print("Test02:", ret)
        ret = con.Test03(ret["int"])
        print("Test03:", ret)
        ret = con.Test04(ret["float"])
        print("Test04:", ret)
        ret = con.Test05(ret["string"])
        print("Test05:", ret)
        ret = con.Test06(ret["bool"], ret["int"], ret["float"], ret["string"])
        print("Test06:", ret)
        ret = con.Test07(ret["struct"])
        print("Test07:", ret)
        ret = con.Test08(ret["map"])
        print("Test08:", ret)
        ret = con.Test09(ret["set"])
        print("Test09:", ret)
        ret_array = []
        for ret in con.Test10(ret["mytype"], _more=True):
            print("Test10:", ret)
            ret_array.append(ret["string"])
        ret = con.Test11(ret_array)
        print("Test11:", ret)
        ret = con.End()
        print("End:", ret)
    print("Certification passed")


######## SERVER #############

service = varlink.Service(
    vendor='Varlink',
    product='Varlink Examples',
    version='1',
    url='http://varlink.org',
    interface_dir=os.path.dirname(__file__)
)


class ServiceRequestHandler(varlink.RequestHandler):
    service = service


def sorted_json(dct):
    if isinstance(dct, type([])):
        return sorted(dct)
    return dct


class CertificationError(varlink.VarlinkError):

    def __init__(self, wants, got):
        varlink.VarlinkError.__init__(self,
                                      {'error': 'org.varlink.certification.CertificationError',
                                       'parameters': {'wants': wants, 'got': got}})


@service.interface('org.varlink.certification')
class CertService(object):
    next_method = {}

    def assert_raw(self, _request, _raw, _message, wants):

        #have = json.loads(wants, object_hook=sorted_json)

        if wants != _message:
            print("Wants", wants, "!= GOT", _message)
            del self.next_method[_request]
            raise CertificationError(wants, json.loads(_raw))

    def assert_cmp(self, _request, _raw, wants, _bool):
        if not _bool:
            del self.next_method[_request]
            raise CertificationError(wants, json.loads(_raw))

    def assert_method(self, _request, from_method, next_method):
        if _request not in self.next_method:
            self.next_method[_request] = "Start"

        if from_method != self.next_method[_request]:
            raise CertificationError("Call to method org.varlink.certification." + self.next_method[_request],
                                     "Call to method org.varlink.certification." + from_method)
        self.next_method[_request] = next_method

    def Start(self, _request=None, _raw=None, _message=None, _oneway=False):
        self.assert_method(_request, "Start", "Test01")
        self.assert_raw(_request, _raw, _message, {
            "oneway": True,
            "method": "org.varlink.certification.Start",
            "parameters": {}
        })

    # () -> (bool: bool)
    def Test01(self, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test01", "Test02")
        self.assert_raw(_request, _raw, _message, {
            "method": "org.varlink.certification.Test01",
            "parameters": {}
        })
        return {"bool": True}

    # (bool: bool) -> (int: int)
    def Test02(self, _bool, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test02", "Test03")
        wants = {
            "method": "org.varlink.certification.Test02",
            "parameters": {"bool": True}
        }
        self.assert_cmp(_request, _raw, wants, _bool == True)
        self.assert_raw(_request, _raw, _message, wants)
        return {"int": 1}

    # (int: int) -> (float: float)
    def Test03(self, _int, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test03", "Test04")
        wants = {
            "method": "org.varlink.certification.Test03",
            "parameters": {"int": 1}
        }
        self.assert_cmp(_request, _raw, wants, _int == 1)
        self.assert_raw(_request, _raw, _message, wants)
        return {"float": 1.0}

    # (float: float) -> (string: string)
    def Test04(self, _float, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test04", "Test05")
        wants = {
            "method": "org.varlink.certification.Test04",
            "parameters": {"float": 1.0}
        }
        self.assert_cmp(_request, _raw, wants, _float == 1.0)
        self.assert_raw(_request, _raw, _message, wants)
        return {"string": "ping"}

    # (string: string) -> (bool: bool, int: int, float: float, string: string)
    def Test05(self, _string, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test05", "Test06")
        wants = {
            "method": "org.varlink.certification.Test05",
            "parameters": {"string": "ping"}
        }
        self.assert_cmp(_request, _raw, wants, _string == "ping")
        self.assert_raw(_request, _raw, _message, wants)
        return {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}

    # (bool: bool, int: int, float: float, string: string)
    # -> (struct: (bool: bool, int: int, float: float, string: string))
    def Test06(self, _bool, _int, _float, _string, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test06", "Test07")
        wants = {
            "method": "org.varlink.certification.Test06",
            "parameters": {
                "bool": False,
                "int": 2,
                "float": math.pi,
                "string": "a lot of string"
            }
        }
        self.assert_raw(_request, _raw, _message, wants)
        self.assert_cmp(_request, _raw, wants, _int == 2)
        self.assert_cmp(_request, _raw, wants, _bool == False)
        self.assert_cmp(_request, _raw, wants, _float == math.pi)
        self.assert_cmp(_request, _raw, wants, _string == "a lot of string")

        return {"struct": {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}}

    # (struct: (bool: bool, int: int, float: float, string: string)) -> (map: [string]string)
    def Test07(self, _dict, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test07", "Test08")
        wants = {
            "method": "org.varlink.certification.Test07",
            "parameters": {
                "struct": {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}
            }
        }
        self.assert_raw(_request, _raw, _message, wants)
        self.assert_cmp(_request, _raw, wants, _dict["int"] == 2)
        self.assert_cmp(_request, _raw, wants, _dict["bool"] == False)
        self.assert_cmp(_request, _raw, wants, _dict["float"] == math.pi)
        self.assert_cmp(_request, _raw, wants, _dict["string"] == "a lot of string")
        return {"map": {"foo": "Foo", "bar": "Bar"}}

    # (map: [string]string) -> (set: [string]())
    def Test08(self, _map, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test08", "Test09")
        self.assert_raw(_request, _raw, _message,
                        {
                            "method": "org.varlink.certification.Test08",
                            "parameters": {"map": {"foo": "Foo", "bar": "Bar"}}
                        })
        return {"set": {"one", "two", "three"}}

    # (set: [string]()) -> (mytype: MyType)
    def Test09(self, _set, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test09", "Test10")
        wants = {
            "method": "org.varlink.certification.Test09",
            "parameters": {
                "set": {"one": {}, "three": {}, "two": {}}
            }
        }
        self.assert_raw(_request, _raw, _message, wants)
        self.assert_cmp(_request, _raw, wants, isinstance(_set, set))
        self.assert_cmp(_request, _raw, wants, len(_set) == 3)
        self.assert_cmp(_request, _raw, wants, "one" in _set)
        self.assert_cmp(_request, _raw, wants, "two" in _set)
        self.assert_cmp(_request, _raw, wants, "three" in _set)
        return {"mytype": {
            "object": {"method": "org.varlink.certification.Test09",
                       "parameters": {"map": {"foo": "Foo", "bar": "Bar"}}},
            "enum": "two",
            "struct": {"first": 1, "second": "2"},
            "array": ["one", "two", "three"],
            "dictionary": {"foo": "Foo", "bar": "Bar"},
            "stringset": {"one", "two", "three"},
            "nullable": None,
            "nullable_array_struct": None,
            "interface": {
                "foo": [
                    None,
                    {"foo": "foo", "bar": "bar"},
                    None,
                    {"one": "foo", "two": "bar"}
                ],
                "anon": {"foo": True, "bar": False}
            }
        }}

    # method Test10(mytype: MyType) -> (string: string)
    def Test10(self, mytype, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test10", "Test11")
        wants = {
            "method": "org.varlink.certification.Test10",
            "more": True,
            "parameters": {
                "object": {"method": "org.varlink.certification.Test09",
                           "parameters": {"map": {"foo": "Foo", "bar": "Bar"}}},
                "enum": "two",
                "struct": {"first": 1, "second": "2"},
                "array": ["one", "two", "three"],
                "dictionary": {"foo": "Foo", "bar": "Bar"},
                "stringset": {"one", "two", "three"},
                "interface": {
                    "foo": [
                        None,
                        {"foo": "foo", "bar": "bar"},
                        None,
                        {"one": "foo", "two": "bar"}
                    ],
                    "anon": {"foo": True, "bar": False}
                }
            }
        }

        if "nullable" in mytype:
            self.assert_cmp(_request, _raw, wants, mytype["nullable"] == None)
            del mytype["nullable"]

        if "nullable_array_struct" in mytype:
            self.assert_cmp(_request, _raw, wants, mytype["nullable_array_struct"] == None)
            del mytype["nullable_array_struct"]

        self.assert_cmp(_request, _raw, wants, mytype == wants["parameters"])

        for i in range(1, 11):
            yield {"string": "Reply number %d" % i, '_continues': i != 10}

    # method Test11(last_more_replies: []string) -> ()
    def Test11(self, last_more_replies, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "Test11", "End")
        wants = {
            "method": "org.varlink.certification.Test11",
            "parameters": {
                "last_more_replies": [
                    "Reply number 1", "Reply number 2", "Reply number 3", "Reply number 4",
                    "Reply number 5", "Reply number 6", "Reply number 7", "Reply number 8",
                    "Reply number 9", "Reply number 10"
                ]
            }
        }
        for i in range(0, 10):
            self.assert_cmp(_request, _raw, wants, last_more_replies[i] == "Reply number %d" % (i + 1))

    # method End() -> ()
    def End(self, _request=None, _raw=None, _message=None):
        self.assert_method(_request, "End", "Start")
        del self.next_method[_request]
        return {"all_ok": True}


def run_server(address):
    with varlink.ThreadingServer(address, ServiceRequestHandler) as server:
        print("Listening on", server.server_address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


######## MAIN #############

def usage():
    print('Usage: %s [[--client] --varlink=<varlink address>]' % sys.argv[0], file=sys.stderr)
    print('\tSelf Exec: $ %s' % sys.argv[0], file=sys.stderr)
    print('\tServer   : $ %s --varlink=<varlink address>' % sys.argv[0], file=sys.stderr)
    print('\tClient   : $ %s --client --varlink=<varlink address>' % sys.argv[0], file=sys.stderr)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["help", "client", "varlink="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    address = None
    client_mode = False

    for opt, arg in opts:
        if opt == "--help":
            usage()
            sys.exit(0)
        elif opt == "--varlink":
            address = arg
        elif opt == "--client":
            client_mode = True

    if not address and not client_mode:
        client_mode = True
        address = 'exec:' + __file__

        if platform != "linux":
            print("varlink exec: not supported on platform %s" % platform, file=sys.stderr)
            usage()
            sys.exit(2)

    if client_mode:
        run_client(address)
    else:
        run_server(address)

    sys.exit(0)


######## UNITTEST #############

class TestService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hasattr(socket, "AF_UNIX"):
            cls.address = "unix:/tmp/org.varlink.certification_" \
                          + str(os.getpid()) \
                          + threading.current_thread().getName()
        else:
            cls.address = "tcp:127.0.0.1:23456"

        cls.server = varlink.ThreadingServer(cls.address, ServiceRequestHandler)
        server_thread = threading.Thread(target=cls.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

    def test_client(self):
        run_client(self.address)

    def test_01(self):
        with varlink.Client(self.address) as client, \
                client.open('org.varlink.certification') as con:
            con.Start(_oneway=True)
            ret = con.Test01()
            print("Test01:", ret)
            ret = con.Test02(ret["bool"])
            print("Test02:", ret)
            self.assertRaises(SyntaxError, con.Test03, "test")
            self.assertRaises(varlink.VarlinkError, con.Test03, 0)
            self.assertRaises(varlink.VarlinkError, con.Test03, ret["int"])
            self.assertRaises(varlink.VarlinkError, con.Start)
            con.Start(_oneway=True)
            ret = con.Test01()
            print("Test01:", ret)
            self.assertRaises(varlink.VarlinkError, con.Start)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
