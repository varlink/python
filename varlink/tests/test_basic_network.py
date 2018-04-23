from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
from future import standard_library
standard_library.install_aliases()
import os
import socket
import threading
import unittest
from sys import platform

import varlink

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
            server.server_close()

    def test_tcp(self):
        self.do_run("tcp:127.0.0.1:23450")

    def test_anon_unix(self):
        if platform == "linux":
            self.do_run("unix:@org.varlink.service_anon_test"
                        + str(os.getpid())
                        + threading.current_thread().getName()
                        )

    def test_unix(self):
        if hasattr(socket, "AF_UNIX"):
            self.do_run("unix:/tmp/org.varlink.service_anon_test_"
                        + str(os.getpid())
                        + threading.current_thread().getName()
                        )

    def test_wrong_url(self):
        self.assertRaises(varlink.ConnectionError, self.do_run,
                          "uenix:/tmp/org.varlink.service_wrong_url_test_%d" % os.getpid())
