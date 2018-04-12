#!/usr/bin/env python3

import json
import os
import signal
import socket
import sys
import threading
from types import SimpleNamespace

from twisted.internet import task
from twisted.internet.defer import Deferred, DeferredQueue, inlineCallbacks
from twisted.internet.endpoints import UNIXClientEndpoint, clientFromString
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

import varlink
from varlink import VarlinkEncoder

with open(os.path.join(os.path.dirname(__file__), 'org.example.more.varlink')) as f:
    INTERFACE_org_example_more = varlink.Interface(f.read())


class VarlinkReceiver(LineReceiver):
    delimiter = b'\0'
    MAX_LENGTH = 8 * 1024 * 1024


class VarlinkClient(VarlinkReceiver, varlink.ClientInterfaceHandler):

    def _send_message(self, out):
        self.sendLine(out)

    def __init__(self):
        self.whenDisconnected = Deferred()
        super().__init__(INTERFACE_org_example_more, namespaced=True)
        self._lock = threading.Lock()
        self.queue = DeferredQueue()
        self._last_method = None

    def lineReceived(self, incoming_message):
        self.queue.put(incoming_message)

    def connectionMade(self):
        pass

    def connectionLost(self, _):
        self.whenDisconnected.callback(None)

    @inlineCallbacks
    def close(self):
        yield self.transport.loseConnection()

    @inlineCallbacks
    def _next_message(self):
        self.resumeProducing()
        msg = yield self.queue.get()
        self.pauseProducing()
        return msg

    @inlineCallbacks
    def replyMore(self):
        if not self._last_method:
            raise Exception("No call before calling reply()/replyMore()")

        message = yield self._next_message()
        message = json.loads(message)
        if 'error' in message and message['error'] != None:
            raise varlink.VarlinkError(message, self._namespaced)
        else:
            return self._interface.filter_params(self._last_method.out_type, self._namespaced, message['parameters'],
                                                 None), \
                   ('continues' in message) \
                   and \
                   message['continues']

    @inlineCallbacks
    def reply(self):
        (ret, more) = yield self.replyMore()
        return ret

    def _add_method(self, method):

        @inlineCallbacks
        def _wrapped(*args, **kwargs):
            self._last_method = method
            parameters = self._interface.filter_params(method.in_type, False, args, kwargs)

            if "_more" in kwargs and kwargs.pop("_more"):
                out = {'method': self._interface.name + "." + method.name, 'more': True, 'parameters': parameters}
            else:
                out = {'method': self._interface.name + "." + method.name, 'parameters': parameters}
            yield self.sendLine(json.dumps(out, cls=varlink.VarlinkEncoder).encode('utf-8'))

        _wrapped.__name__ = method.name
        _wrapped.__doc__ = "Varlink call: " + method.signature
        setattr(self, method.name, _wrapped)


CHILD_PID = 0


def sigterm_handler(signum, _):
    global CHILD_PID
    if signum == signal.SIGTERM and CHILD_PID:
        try:
            os.kill(CHILD_PID, signal.SIGTERM)
        except OSError:
            pass
        os.waitpid(CHILD_PID, 0)
        CHILD_PID = 0


def varlink_filter_exec_address(address):
    global CHILD_PID
    if address.startswith("exec:"):
        executable = address[5:]
        s = socket.socket(socket.AF_UNIX)
        s.setblocking(0)
        s.bind("")
        s.listen()
        address = s.getsockname().decode('ascii')

        CHILD_PID = os.fork()
        if CHILD_PID == 0:
            # child
            n = s.fileno()
            if n == 3:
                # without dup() the socket is closed with the python destructor
                n = os.dup(3)
                del s
            else:
                try:
                    os.close(3)
                except OSError:
                    pass

            os.dup2(n, 3)
            address = address.replace('\0', '@', 1)
            address = "--varlink=unix:%s;mode=0600" % address
            os.environ["LISTEN_FDS"] = "1"
            os.environ["LISTEN_FDNAMES"] = "varlink"
            os.environ["LISTEN_PID"] = str(os.getpid())
            os.execlp(executable, executable, address)
            sys.exit(1)
        # parent
        s.close()
        signal.signal(signal.SIGALRM, sigterm_handler)
        address = "unix:%s" % address
        address = address.replace('\0', '@', 1)

    return address


def varlink_to_twisted_endpoint(reactor, _address):
    global CHILD_PID

    if _address.startswith("unix:"):
        address = _address[5:]
        address = address.replace(';mode=', ':mode=')
        address = address.replace('@', '\0', 1)
        # serverFromString() doesn't handle the zero byte
        return UNIXClientEndpoint(reactor, address)
    elif _address.startswith("tcp:"):
        address = _address[4:]
        p = address.rfind(':')
        if p != -1:
            port = address[p + 1:]
            address = address[:p]
        else:
            raise Exception("Invalid address '%s'" % _address)
        address = address.replace(':', r'\:')
        address = address.replace('[', '')
        address = address.replace(']', '')
        address = "tcp:" + address + ":" + port
        return clientFromString(reactor, address)
    else:
        raise Exception("Invalid address '%s'" % _address)


@inlineCallbacks
def main(reactor, address):
    factory = Factory.forProtocol(VarlinkClient)
    endpoint1 = varlink_to_twisted_endpoint(reactor, address)
    endpoint2 = varlink_to_twisted_endpoint(reactor, address)

    try:
        con1 = yield endpoint1.connect(factory)
        con2 = yield endpoint2.connect(factory)

        yield con1.TestMap({"one": "one", "two": "two"})
        ret = yield con1.reply()
        # print(ret)
        assert ret.map == {'one': SimpleNamespace(i=1, val='one'), 'two': SimpleNamespace(i=2, val='two')}

        yield con1.TestObject(ret)
        jret = yield con1.reply()

        jret = json.dumps(jret.object, cls=VarlinkEncoder)
        jcmp = json.dumps(ret, cls=VarlinkEncoder)
        assert jcmp == jret

        yield con1.TestMore(10, _more=True)
        while True:
            (m, more) = yield con1.replyMore()

            if hasattr(m.state, 'start'):
                if m.state.start and m.state.start != None:
                    print("--- Start ---", file=sys.stderr)

            if hasattr(m.state, 'end') and m.state.end != None:
                if m.state.end:
                    print("--- End ---", file=sys.stderr)

            if hasattr(m.state, 'progress') and m.state.progress != None:
                print("Progress:", m.state.progress, file=sys.stderr)
                if m.state.progress > 50:
                    yield con2.Ping("Test")
                    ret = yield con2.reply()
                    print("Ping: ", ret.pong)

            if not more:
                break

        yield con1.close()
        yield con2.close()
        reactor.stop()
    except ConnectionError as e:
        import traceback
        print("ConnectionError", e, file=sys.stderr)
        traceback.print_exception(type(e), e, e.__traceback__)
        raise e
    except varlink.VarlinkError as e:
        print(e, file=sys.stderr)
        print(e.error(), file=sys.stderr)
        print(e.parameters(), file=sys.stderr)
        raise e


if __name__ == '__main__':
    listen_fd = None

    if len(sys.argv) == 2:
        connect_address = sys.argv[1]
    else:
        connect_address = 'exec:./server-twisted.py'

    print('Connecting to %s\n' % connect_address)
    connect_address = varlink_filter_exec_address(connect_address)

    task.react(main, [connect_address])

    if CHILD_PID != 0:
        try:
            os.kill(CHILD_PID, signal.SIGTERM)
        except OSError:
            pass
        os.waitpid(CHILD_PID, 0)
