#!/usr/bin/python3

import os
import stat
import sys
import time

import varlink

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
            print("ERROR", error, file=sys.stderr)

    def Ping(self, ping):
        return {'pong': ping}

    def StopServing(self):
        print("Server ends.")
        sys.exit(0)


if len(sys.argv) < 2:
    print('missing address parameter')
    sys.exit(1)

listen_fd = None

try:
    if stat.S_ISSOCK(os.fstat(3).st_mode):
        listen_fd = 3
except OSError:
    pass

with varlink.SimpleServer(service) as s:
    print("Listening on", sys.argv[1])
    try:
        s.serve(sys.argv[1], listen_fd=listen_fd)
    except KeyboardInterrupt:
        pass
