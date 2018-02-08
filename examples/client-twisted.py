#!/usr/bin/python3

import json
import threading
import os
import sys
import varlink
import socket
import signal

from twisted.internet import task
from twisted.internet.defer import Deferred, DeferredQueue, inlineCallbacks
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import clientFromString
from twisted.protocols.basic import LineReceiver
from types import SimpleNamespace

with open(os.path.join(os.path.dirname(__file__), 'org.varlink.example.more.varlink')) as f:
    INTERFACE_org_varlink_example_more = varlink.Interface(f.read())


class VarlinkReceiver(LineReceiver):
    delimiter = b'\0'
    MAX_LENGTH = 8 * 1024 * 1024


class VarlinkClient(VarlinkReceiver, varlink.ClientInterfaceHandler):
    def __init__(self):
        self.whenDisconnected = Deferred()
        super().__init__(INTERFACE_org_varlink_example_more, namespaced=True)
        self._lock = threading.Lock()
        self.queue = DeferredQueue()

    def lineReceived(self, incoming_message):
        self.queue.put(incoming_message)

    def connectionMade(self):
        pass

    def connectionLost(self, reason):
        self.whenDisconnected.callback(None)

    @inlineCallbacks
    def close(self):
        yield self.transport.loseConnection()

    @inlineCallbacks
    def _nextMessage(self):
        self.resumeProducing()
        msg = yield self.queue.get()
        self.pauseProducing()
        return msg

    @inlineCallbacks
    def replyMore(self):
        message = yield self._nextMessage()
        if self._namespaced:
            message = json.loads(message, object_hook=lambda d: SimpleNamespace(**d))
            if hasattr(message, "error"):
                raise varlink.VarlinkError(message, self._namespaced)
            else:
                return (message.parameters, hasattr(message, "continues") and message.continues)
        else:
            message = json.loads(message)
            if 'error' in message:
                raise varlink.VarlinkError(message, self._namespaced)
            else:
                return (message['parameters'], ('continues' in message) and message['continues'])

    @inlineCallbacks
    def reply(self):
        (ret, more) = yield self.replyMore()
        return ret

    def _add_method(self, method):
        @inlineCallbacks
        def _wrapped(*args, **kwargs):
            sparam = self._interface.filter_params(method.in_type, args, kwargs)

            if "_more" in kwargs and kwargs.pop("_more"):
                out = {'method': self._interface._name + "." + method.name, 'more': True, 'parameters': sparam}
            else:
                out = {'method': self._interface._name + "." + method.name, 'parameters': sparam}
            yield self.sendLine(json.dumps(out, cls=varlink.VarlinkEncoder).encode('utf-8'))

        _wrapped.__name__ = method.name
        _wrapped.__doc__ = "Varlink call: " + method.signature
        setattr(self, method.name, _wrapped)


CHILDPID = 0


def sigterm_handler(signum, frame):
    global CHILDPID
    if signum == signal.SIGTERM and CHILDPID:
        try:
            os.kill(CHILDPID, signal.SIGTERM)
        except OSError:
            pass
        os.waitpid(CHILDPID, 0)
        CHILDPID = 0


def varlink_to_twisted_address(address):
    global CHILDPID

    if address.startswith("unix:"):
        address.replace(';mode=', ':mode=')
    elif address.startswith("ip:"):
        address = address[3:]
        p = address.rfind(":")
        port = address[p + 1:]
        address = address[:p]
        address = "tcp:%s:interface=%s" % (port, address)
    elif address.startswith("exec:"):
        executable = address[5:]
        s = socket.socket(socket.AF_UNIX)
        s.setblocking(0)
        s.bind("")
        s.listen()
        address = s.getsockname().decode('ascii')

        CHILDPID = os.fork()
        if CHILDPID == 0:
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
            address = "unix:%s;mode=0600" % address
            os.execlp(executable, executable, address)
            sys.exit(1)
        # parent
        s.close()

        signal.signal(signal.SIGALRM, sigterm_handler)
        address = "unix:%s" % address

    else:
        raise Exception("Invalid address '%s'" % address)

    return address


@inlineCallbacks
def main(reactor, address):
    factory = Factory.forProtocol(VarlinkClient)
    endpoint1 = clientFromString(reactor, address)
    endpoint2 = clientFromString(reactor, address)

    try:
        con1 = yield endpoint1.connect(factory)
        con2 = yield endpoint2.connect(factory)
        yield con1.TestMore(10, _more=True)
        while True:
            (m, more) = yield con1.replyMore()

            if hasattr(m.state, 'start'):
                if m.state.start:
                    print("--- Start ---", file=sys.stderr)

            if hasattr(m.state, 'progress'):
                print("Progress:", m.state.progress, file=sys.stderr)
                if m.state.progress > 50:
                    yield con2.Ping("Test")
                    ret = yield con2.reply()
                    print("Ping: ", ret.pong)

            if hasattr(m.state, 'end'):
                if m.state.end:
                    print("--- End ---", file=sys.stderr)

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
        address = sys.argv[1]
    else:
        address = 'exec:./server-twisted.py'

    print('Connecting to %s\n' % address)
    address = varlink_to_twisted_address(address)

    task.react(main, [address])

    if CHILDPID != 0:
        try:
            os.kill(CHILDPID, signal.SIGTERM)
        except OSError:
            pass
        os.waitpid(CHILDPID, 0)
