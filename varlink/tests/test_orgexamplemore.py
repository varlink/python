#!/usr/bin/env python

"""Server and Client example of varlink for python

From the main git repository directory run::

    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py

or::

    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py --varlink="unix:@test" &
    Listening on @test
    [1] 6434
    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py --client --varlink="unix:@test"
    [...]

"""

from __future__ import print_function
from __future__ import unicode_literals

import getopt
import os
import shlex
import socket
import sys
import threading
import time
import unittest
from sys import platform

from builtins import int
from builtins import next
from builtins import object
from builtins import range

import varlink


######## CLIENT #############

def run_client(client):
    print('Connecting to %s\n' % client)
    try:
        with \
                client.open('org.example.more', namespaced=True) as con1, \
                client.open('org.example.more', namespaced=True) as con2:

            for m in con1.TestMore(10, _more=True):
                if hasattr(m.state, 'start') and m.state.start != None:
                    if m.state.start:
                        print("--- Start ---", file=sys.stderr)

                if hasattr(m.state, 'end') and m.state.end != None:
                    if m.state.end:
                        print("--- End ---", file=sys.stderr)

                if hasattr(m.state, 'progress') and m.state.progress != None:
                    print("Progress:", m.state.progress, file=sys.stderr)
                    if m.state.progress > 50:
                        ret = con2.Ping("Test")
                        print("Ping: ", ret.pong)

    except varlink.ConnectionError as e:
        print("ConnectionError:", e)
        raise e
    except varlink.VarlinkError as e:
        print(e)
        print(e.error())
        print(e.parameters())
        raise e


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


class ActionFailed(varlink.VarlinkError):

    def __init__(self, reason):
        varlink.VarlinkError.__init__(self,
                                      {'error': 'org.example.more.ActionFailed',
                                       'parameters': {'field': reason}})


@service.interface('org.example.more')
class Example(object):
    sleep_duration = 1

    def TestMore(self, n, _more=True, _server=None):
        try:
            if not _more:
                yield varlink.InvalidParameter('more')

            yield {'state': {'start': True}, '_continues': True}

            for i in range(0, n):
                yield {'state': {'progress': int(i * 100 / n)}, '_continues': True}
                time.sleep(self.sleep_duration)

            yield {'state': {'progress': 100}, '_continues': True}

            yield {'state': {'end': True}, '_continues': False}
        except Exception as error:
            print("ERROR", error, file=sys.stderr)
            if _server:
                _server.shutdown()

    def Ping(self, ping):
        return {'pong': ping}

    def StopServing(self, _request=None, _server=None):
        print("Server ends.")

        if _request:
            print("Shutting down client connection")
            _server.shutdown_request(_request)

        if _server:
            print("Shutting down server")
            _server.shutdown()

    def TestMap(self, map):
        i = 1
        ret = {}
        for (key, val) in map.items():
            ret[key] = {"i": i, "val": val}
            i += 1
        return {'map': ret}

    def TestObject(self, object):
        import json
        return {"object": json.loads(json.dumps(object))}


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
    def test_service(self):
        address = "tcp:127.0.0.1:23451"
        Example.sleep_duration = 0.1

        server = varlink.ThreadingServer(address, ServiceRequestHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        try:
            client = varlink.Client.new_with_address(address)

            run_client(client)

            with \
                    client.open('org.example.more', namespaced=True) as con1, \
                    client.open('org.example.more', namespaced=True) as con2:

                self.assertEqual(con1.Ping("Test").pong, "Test")

                it = con1.TestMore(10, _more=True)

                m = next(it)
                self.assertTrue(hasattr(m.state, 'start'))
                self.assertFalse(hasattr(m.state, 'end'))
                self.assertFalse(hasattr(m.state, 'progress'))
                self.assertIsNotNone(m.state.start)

                for i in range(0, 110, 10):
                    m = next(it)
                    self.assertTrue(hasattr(m.state, 'progress'))
                    self.assertFalse(hasattr(m.state, 'start'))
                    self.assertFalse(hasattr(m.state, 'end'))
                    self.assertIsNotNone(m.state.progress)
                    self.assertEqual(i, m.state.progress)

                    if i > 50:
                        ret = con2.Ping("Test")
                        self.assertEqual("Test", ret.pong)

                m = next(it)
                self.assertTrue(hasattr(m.state, 'end'))
                self.assertFalse(hasattr(m.state, 'start'))
                self.assertFalse(hasattr(m.state, 'progress'))
                self.assertIsNotNone(m.state.end)

                self.assertRaises(StopIteration, next, it)

                con1.StopServing(_oneway=True)
                time.sleep(0.5)
                self.assertRaises(varlink.ConnectionError, con1.Ping, "Test")
        finally:
            server.shutdown()
            server.server_close()
