#!/usr/bin/env python

from __future__ import print_function
from __future__ import unicode_literals

import codecs
import getopt
import json
import math
import os
import shlex
import socket
import sys
import threading
import time
import unittest
from sys import platform

try:
    from builtins import object
    from builtins import range
    from builtins import str
except ImportError:
    pass

import varlink


######## CLIENT #############

def run_client(client):
    print('Connecting to %s\n' % client)
    with client.open('org.varlink.certification') as con:
        ret = con.Start()
        client_id = ret["client_id"]
        print("client_id:", client_id)
        ret = con.Test01(client_id)
        print("Test01:", ret)
        ret = con.Test02(client_id, ret["bool"])
        print("Test02:", ret)
        ret = con.Test03(client_id, ret["int"])
        print("Test03:", ret)
        ret = con.Test04(client_id, ret["float"])
        print("Test04:", ret)
        ret = con.Test05(client_id, ret["string"])
        print("Test05:", ret)
        ret = con.Test06(client_id, ret["bool"], ret["int"], ret["float"], ret["string"])
        print("Test06:", ret)
        ret = con.Test07(client_id, ret["struct"])
        print("Test07:", ret)
        ret = con.Test08(client_id, ret["map"])
        print("Test08:", ret)
        ret = con.Test09(client_id, ret["set"])
        print("Test09:", ret)
        ret_array = []
        for ret in con.Test10(client_id, ret["mytype"], _more=True):
            print("Test10:", ret)
            ret_array.append(ret["string"])
        ret = con.Test11(client_id, ret_array, _oneway=True)
        print("Test11:", ret)
        ret = con.End(client_id)
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

    def new_client_id(self, _server):
        client_id = codecs.getencoder('hex')(os.urandom(16))[0].decode("ascii")
        if not hasattr(_server, "next_method"):
            _server.next_method = {}
        if not hasattr(_server, "lifetimes"):
            _server.lifetimes = []

        _server.next_method[client_id] = "Start"
        _server.lifetimes.append((time.time(), client_id))
        return client_id

    def check_lifetimes(self, _server):
        if not hasattr(_server, "lifetimes"):
            return

        now = time.time()
        while True:
            if len(_server.lifetimes) == 0:
                return

            (t, client_id) = _server.lifetimes[0]
            if (now - t) < (60 * 60 * 12):
                return

            del _server.lifetimes[0]
            if hasattr(_server, "next_method") and client_id in _server.next_method:
                del _server.next_method[client_id]

    def assert_raw(self, client_id, _server, _raw, _message, wants):
        if wants != _message:
            del _server.next_method[client_id]
            raise CertificationError(wants, json.loads(_raw.decode('utf-8')))

    def assert_cmp(self, client_id, _server, _raw, wants, _bool):
        if not _bool:
            del _server.next_method[client_id]
            raise CertificationError(wants, json.loads(_raw.decode('utf-8')))

    def assert_method(self, client_id, _server, from_method, next_method):
        if not hasattr(_server, "next_method") or client_id not in _server.next_method:
            raise CertificationError({"method": "org.varlink.certification.Start+++"},
                                     {"method": "org.varlink.certification." + from_method})

        self.check_lifetimes(_server)

        if from_method != _server.next_method[client_id]:
            raise CertificationError("Call to method org.varlink.certification." + _server.next_method[client_id],
                                     "Call to method org.varlink.certification." + from_method)
        _server.next_method[client_id] = next_method

    def Start(self, _server=None, _raw=None, _message=None, _oneway=False):
        client_id = self.new_client_id(_server)
        if 'parameters' in _message and not _message['parameters']:
            del _message['parameters']
        self.assert_method(client_id, _server, "Start", "Test01")
        self.assert_raw(client_id, _server, _raw, _message, {
            "method": "org.varlink.certification.Start",
        })
        return {"client_id": client_id}

    # () -> (bool: bool)
    def Test01(self, client_id, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test01", "Test02")
        self.assert_raw(client_id, _server, _raw, _message, {
            "method": "org.varlink.certification.Test01",
            "parameters": {"client_id": client_id}
        })
        return {"bool": True}

    # (bool: bool) -> (int: int)
    def Test02(self, client_id, _bool, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test02", "Test03")
        wants = {
            "method": "org.varlink.certification.Test02",
            "parameters": {"client_id": client_id, "bool": True}
        }
        self.assert_cmp(client_id, _server, _raw, wants, _bool == True)
        self.assert_raw(client_id, _server, _raw, _message, wants)
        return {"int": 1}

    # (int: int) -> (float: float)
    def Test03(self, client_id, _int, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test03", "Test04")
        wants = {
            "method": "org.varlink.certification.Test03",
            "parameters": {"client_id": client_id, "int": 1}
        }
        self.assert_cmp(client_id, _server, _raw, wants, _int == 1)
        self.assert_raw(client_id, _server, _raw, _message, wants)
        return {"float": 1.0}

    # (float: float) -> (string: string)
    def Test04(self, client_id, _float, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test04", "Test05")
        wants = {
            "method": "org.varlink.certification.Test04",
            "parameters": {"client_id": client_id, "float": 1.0}
        }
        self.assert_cmp(client_id, _server, _raw, wants, _float == 1.0)
        self.assert_raw(client_id, _server, _raw, _message, wants)
        return {"string": "ping"}

    # (string: string) -> (bool: bool, int: int, float: float, string: string)
    def Test05(self, client_id, _string, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test05", "Test06")
        wants = {
            "method": "org.varlink.certification.Test05",
            "parameters": {"client_id": client_id, "string": "ping"}
        }
        self.assert_cmp(client_id, _server, _raw, wants, _string == "ping")
        self.assert_raw(client_id, _server, _raw, _message, wants)
        return {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}

    # (bool: bool, int: int, float: float, string: string)
    # -> (struct: (bool: bool, int: int, float: float, string: string))
    def Test06(self, client_id, _bool, _int, _float, _string, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test06", "Test07")
        wants = {
            "method": "org.varlink.certification.Test06",
            "parameters": {
                "client_id": client_id,
                "bool": False,
                "int": 2,
                "float": math.pi,
                "string": "a lot of string"
            }
        }
        self.assert_raw(client_id, _server, _raw, _message, wants)
        self.assert_cmp(client_id, _server, _raw, wants, _int == 2)
        self.assert_cmp(client_id, _server, _raw, wants, _bool == False)
        self.assert_cmp(client_id, _server, _raw, wants, _float == math.pi)
        self.assert_cmp(client_id, _server, _raw, wants, _string == "a lot of string")

        return {"struct": {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}}

    # (struct: (bool: bool, int: int, float: float, string: string)) -> (map: [string]string)
    def Test07(self, client_id, _dict, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test07", "Test08")
        wants = {
            "method": "org.varlink.certification.Test07",
            "parameters": {
                "client_id": client_id,
                "struct": {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}
            }
        }
        self.assert_raw(client_id, _server, _raw, _message, wants)
        self.assert_cmp(client_id, _server, _raw, wants, _dict["int"] == 2)
        self.assert_cmp(client_id, _server, _raw, wants, _dict["bool"] == False)
        self.assert_cmp(client_id, _server, _raw, wants, _dict["float"] == math.pi)
        self.assert_cmp(client_id, _server, _raw, wants, _dict["string"] == "a lot of string")
        return {"map": {"foo": "Foo", "bar": "Bar"}}

    # (map: [string]string) -> (set: [string]())
    def Test08(self, client_id, _map, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test08", "Test09")
        self.assert_raw(client_id, _server, _raw, _message,
                        {
                            "method": "org.varlink.certification.Test08",
                            "parameters": {"client_id": client_id, "map": {"foo": "Foo", "bar": "Bar"}}
                        })
        return {"set": {"one", "two", "three"}}

    # (set: [string]()) -> (mytype: MyType)
    def Test09(self, client_id, _set, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test09", "Test10")
        wants = {
            "method": "org.varlink.certification.Test09",
            "parameters": {
                "client_id": client_id,
                "set": {"one": {}, "three": {}, "two": {}}
            }
        }
        self.assert_raw(client_id, _server, _raw, _message, wants)
        self.assert_cmp(client_id, _server, _raw, wants, isinstance(_set, set))
        self.assert_cmp(client_id, _server, _raw, wants, len(_set) == 3)
        self.assert_cmp(client_id, _server, _raw, wants, "one" in _set)
        self.assert_cmp(client_id, _server, _raw, wants, "two" in _set)
        self.assert_cmp(client_id, _server, _raw, wants, "three" in _set)
        return {
            "client_id": client_id,
            "mytype": {
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
            }
        }

    # method Test10(mytype: MyType) -> (string: string)
    def Test10(self, client_id, mytype, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "Test10", "Test11")

        wants = {
            "method": "org.varlink.certification.Test10",
            "more": True,
            "parameters": {
                "client_id": client_id,
                "mytype": {
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
        }

        if "nullable" in mytype:
            self.assert_cmp(client_id, _server, _raw, wants, mytype["nullable"] == None)
            del mytype["nullable"]

        if "nullable_array_struct" in mytype:
            self.assert_cmp(client_id, _server, _raw, wants, mytype["nullable_array_struct"] == None)
            del mytype["nullable_array_struct"]

        self.assert_cmp(client_id, _server, _raw, wants, mytype == wants["parameters"]["mytype"])

        for i in range(1, 11):
            yield {"string": "Reply number %d" % i, '_continues': i != 10}

    # method Test11(last_more_replies: []string) -> ()
    def Test11(self, client_id, last_more_replies, _server=None, _raw=None, _message=None, _oneway=False):
        self.assert_method(client_id, _server, "Test11", "End")
        wants = {
            "oneway": True,
            "method": "org.varlink.certification.Test11",
            "parameters": {
                "client_id": client_id,
                "last_more_replies": [
                    "Reply number 1", "Reply number 2", "Reply number 3", "Reply number 4",
                    "Reply number 5", "Reply number 6", "Reply number 7", "Reply number 8",
                    "Reply number 9", "Reply number 10"
                ]
            }
        }

        self.assert_cmp(client_id, _server, _raw, wants, _oneway)

        for i in range(0, 10):
            self.assert_cmp(client_id, _server, _raw, wants, last_more_replies[i] == "Reply number %d" % (i + 1))

    # method End() -> ()
    def End(self, client_id, _server=None, _raw=None, _message=None):
        self.assert_method(client_id, _server, "End", "Start")

        self.assert_raw(client_id, _server, _raw, _message, {
            "method": "org.varlink.certification.End",
            "parameters": {"client_id": client_id}
        })

        del _server.next_method[client_id]
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
    print('\tClient   : $ %s --client --bridge=<bridge command>' % sys.argv[0], file=sys.stderr)
    print('\tClient   : $ %s --client --activate=<activation command>' % sys.argv[0], file=sys.stderr)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "b:A:", ["help", "client", "varlink=", "bridge=", "activate="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    address = None
    client_mode = False
    activate = None
    bridge = None

    for opt, arg in opts:
        if opt == "--help":
            usage()
            sys.exit(0)
        elif opt == "--varlink":
            address = arg
        elif opt == "--bridge" or opt == "-b":
            bridge = arg
        elif opt == "--activate" or opt == "-A":
            activate = arg
        elif opt == "--client":
            client_mode = True

    client = None

    if client_mode:
        if bridge:
            client = varlink.Client.new_with_bridge(shlex.split(bridge))
        if activate:
            client = varlink.Client.new_with_activate(shlex.split(activate))
        if address:
            client = varlink.Client.new_with_address(address)

    if not address and not client_mode:
        if not hasattr(socket, "AF_UNIX"):
            print("varlink activate: not supported on platform %s" % platform, file=sys.stderr)
            usage()
            sys.exit(2)

        client_mode = True
        with varlink.Client.new_with_activate([__file__, "--varlink=$VARLINK_ADDRESS"]) as client:
            run_client(client)
    elif client_mode:
        with client:
            run_client(client)
    else:
        run_server(address)

    sys.exit(0)


######## UNITTEST #############

class TestService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hasattr(socket, "AF_UNIX"):
            cls.address = "unix:org.varlink.certification_" \
                          + str(os.getpid()) \
                          + threading.current_thread().getName()
        else:
            cls.address = "tcp:127.0.0.1:23456"

        cls.server = varlink.ThreadingServer(cls.address, ServiceRequestHandler)
        server_thread = threading.Thread(target=cls.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

    def test_client(self):
        run_client(varlink.Client.new_with_address(self.address))

    def test_01(self):
        with varlink.Client(self.address) as client, \
                client.open('org.varlink.certification') as con:
            ret = con.Start()
            client_id = ret["client_id"]
            ret = con.Test01(client_id)
            print("Test01:", ret)
            ret = con.Test02(client_id, ret["bool"])
            print("Test02:", ret)
            self.assertRaises(varlink.VarlinkError, con.Test03, "test")
            self.assertRaises(varlink.VarlinkError, con.Test03, client_id, 0)
            self.assertRaises(varlink.VarlinkError, con.Test03, client_id, ret["int"])
            ret = con.Start()
            client_id = ret["client_id"]
            ret = con.Test01(client_id)
            print("Test01:", ret)
            ret = con.Test02(client_id, ret["bool"])
            print("Test02:", ret)
            self.assertRaises(varlink.VarlinkError, con.Test01, client_id)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
