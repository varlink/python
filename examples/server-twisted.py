#!/usr/bin/env python3

import os
import sys
import threading
import time

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString, UNIXServerEndpoint
from twisted.internet.protocol import ServerFactory
from twisted.internet.threads import deferToThread
from twisted.protocols.basic import LineReceiver

import varlink

service = varlink.Service(
    vendor='Varlink',
    product='Varlink Examples',
    version='1',
    url="http://varlink.org",
    interface_dir=os.path.dirname(__file__)
)


class ActionFailed(varlink.VarlinkError):

    def __init__(self, reason):
        varlink.VarlinkError.__init__(self,
                                      {'error': 'org.example.more.ActionFailed',
                                       'parameters': {'field': reason}})


@service.interface('org.example.more')
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

    def StopServing(self):
        print("Server ends.")
        reactor.stop()

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


def varlink_to_twisted_endpoint(address):
    if address.startswith("unix:"):
        mode = None
        address = address[5:]
        m = address.rfind(';mode=')
        if m != -1:
            mode = address[m + 6:]
            address = address[:m]

        if address[0] == '@':
            # serverFromString() doesn't handle the zero byte
            address = address.replace('@', '\0', 1)
            mode = None
        if mode:
            return UNIXServerEndpoint(reactor, address, mode=int(mode, 8))
        else:
            return UNIXServerEndpoint(reactor, address)

    elif address.startswith("tcp:"):
        address = address[4:]
        p = address.rfind(":")
        port = address[p + 1:]
        address = address[:p]
        address = address.replace(':', r'\:')
        address = address.replace('[', '')
        address = address.replace(']', '')
        address = "tcp:%s:interface=%s" % (port, address)
        return serverFromString(reactor, address)
    else:
        raise Exception("Invalid address '%s'" % address)


if __name__ == '__main__':
    if len(sys.argv) < 2 or not sys.argv[1].startswith("--varlink="):
        print('Usage: %s --varlink=<varlink address>' % sys.argv[0])
        sys.exit(1)

    try:
        endpoint = serverFromString(reactor, "systemd:domain=UNIX:index=0")
    except:
        endpoint = None

    if endpoint:
        endpoint.listen(VarlinkServerFactory())
        print("Listening on LISTEN_FDS", sys.argv[1][10:])
    else:
        endpoint = varlink_to_twisted_endpoint(sys.argv[1][10:])
        endpoint.listen(VarlinkServerFactory())
        print("Listening on", sys.argv[1][10:])

    reactor.run()
