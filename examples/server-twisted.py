#!/usr/bin/python3

import threading
import os
import stat
import sys
import varlink
import time
import socket

from twisted.internet import reactor
from twisted.internet.threads import deferToThread
from twisted.internet.protocol import ServerFactory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver

service = varlink.Service(
    vendor='Varlink',
    product='Varlink Examples',
    version='1',
    interface_dir=os.path.dirname(__file__)
)


class ActionFailed(varlink.VarlinkError):
    def __init__(self, reason):
        varlink.VarlinkError.__init__(self,
                                      {'error': 'org.varlink.example.more.ActionFailed',
                                       'parameters': {'field': reason}})


@service.interface('org.varlink.example.more')
class Example:
    def TestMore(self, n, _more=True):
        try:
            if not _more:
                yield varlink.InvalidParameter('more')

            yield {'state': {'start': True}, '_continues': True}

            for i in range(0, n):
                yield {'state': {'progress': int(i * 100 / n)}, '_continues': True}
                time.sleep(1)

            yield {'state': {'progress': 100}, '_continues': True}

            yield {'state': {'end': True}, '_continues': False}
        except Exception as error:
            print("ERROR", type(error), file=sys.stderr)

    def Ping(self, ping):
        return {'pong': ping}


class VarlinkReceiver(LineReceiver):
    delimiter = b'\0'
    MAX_LENGTH = 8 * 1024 * 1024


class VarlinkServer(VarlinkReceiver):
    def __init__(self, _service):
        self._service = _service
        self._lock = threading.Lock()
        self._disconnected = False

    def connectionLost(self, _):
        self._disconnected = True

    def sendMessages(self, out):
        if self._disconnected:
            return
        for o in out:
            if self._disconnected:
                return
            self.sendLine(o)

    def messagesSent(self, _):
        self.resumeProducing()

    def lineReceived(self, incoming_message):
        deferToThread(self.sendMessages, self._service.handle(incoming_message))


class VarlinkServerFactory(ServerFactory):
    def protocol(self):
        return VarlinkServer(service)


def varlink_to_twisted_address(address):
    if address.startswith("unix:"):
        address = address.replace('@', '\0', 1)
        address = address.replace(';mode=', ':mode=')
    elif address.startswith("ip:"):
        address = address[3:]
        p = address.rfind(":")
        port = address[p + 1:]
        address = address[:p]
        address = "tcp:%s:interface=%s" % (port, address)
    else:
        raise Exception("Invalid address '%s'" % address)

    return address


if __name__ == '__main__':
    listen_fd = None
    if len(sys.argv) < 2:
        print('missing address parameter', file=sys.stderr)
        sys.exit(1)

    try:
        if stat.S_ISSOCK(os.fstat(3).st_mode):
            listen_fd = 3
    except OSError:
        listen_fd = None

    if listen_fd:
        reactor.adoptStreamPort(listen_fd, socket.AF_UNIX, VarlinkServerFactory())
    else:
        connect_address = varlink_to_twisted_address(sys.argv[1])
        endpoint = serverFromString(reactor, connect_address)
        endpoint.listen(VarlinkServerFactory())

    print("Listening on", sys.argv[1])
    reactor.run()
