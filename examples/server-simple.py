#!/usr/bin/env python3

import os
import sys
import time

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
            print("ERROR", error, file=sys.stderr)

    def Ping(self, ping):
        return {'pong': ping}

    def StopServing(self, _server = None):
        yield {}
        print("Server ends.")
        if _server:
            _server.shutdown()
        sys.exit(0)

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


if __name__ == '__main__':
    if len(sys.argv) < 2 or not sys.argv[1].startswith("--varlink="):
        print('Usage: %s --varlink=<varlink address>' % sys.argv[0])
        sys.exit(1)

    with varlink.ThreadingServer(sys.argv[1][10:], ServiceRequestHandler) as server:
        print("Listening on", server.server_address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    sys.exit(0)
