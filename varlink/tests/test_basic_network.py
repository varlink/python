# /usr/bin/env python3

import varlink
import os
import unittest
import threading
from sys import platform

service = varlink.Service(
    vendor='Varlink',
    product='Varlink Examples',
    version='1',
    url='http://varlink.org',
    interface_dir=os.path.dirname(__file__)
)


class ServiceRequestHandler(varlink.RequestHandler):
    service = service


class TestService(unittest.TestCase):
    def do_run(self, address):
        server = varlink.ThreadingServer(address, ServiceRequestHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            with varlink.Client(address) as client, \
                    client.open('org.varlink.service') as _connection:
                info = _connection.GetInfo()

                self.assertEqual(len(info['interfaces']), 1)
                self.assertEqual(info['interfaces'][0], "org.varlink.service")
                self.assertEqual(info, service.GetInfo())

                desc = _connection.GetInterfaceDescription(info['interfaces'][0])
                self.assertEqual(desc, service.GetInterfaceDescription("org.varlink.service"))

                _connection.close()

        finally:
            server.shutdown()

    def test_tcp(self):
        self.do_run("tcp:127.0.0.1:23450")

    def test_anon_unix(self):
        if platform == "linux":
            self.do_run("unix:@org.varlink.service_anon_test")

    def test_unix(self):
        self.do_run("unix:/tmp/org.varlink.service_anon_test_%d" % os.getpid())

    def test_wrong_url(self):
        self.assertRaises(ConnectionError, self.do_run,
                          "uenix:/tmp/org.varlink.service_wrong_url_test_%d" % os.getpid())
