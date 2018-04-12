#!/usr/bin/env python3

import sys
import json
import unittest

from varlink import (Client, VarlinkError, VarlinkEncoder)
from types import SimpleNamespace

if len(sys.argv) == 2:
    address = sys.argv[1]
else:
    address = 'exec:./server-simple.py'

print('Connecting to %s\n' % address)
try:
    with Client(address=address) as client, \
            client.open('org.example.more', namespaced=True) as con1, \
            client.open('org.example.more', namespaced=True) as con2:
        ret = con1.TestMap({"one": "one", "two": "two"})
        # print(ret)
        assert ret.map == {"one": SimpleNamespace(i=1, val="one"), "two": SimpleNamespace(i=2, val="two")}

        jret = con1.TestObject(ret)
        jret = json.dumps(jret.object, cls=VarlinkEncoder)
        jcmp = json.dumps(ret, cls=VarlinkEncoder)
        assert jcmp == jret

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

except ConnectionError as e:
    print(e)
    sys.exit(1)
except VarlinkError as e:
    print(e)
    print(e.error())
    print(e.parameters())
    sys.exit(1)
except KeyboardInterrupt:
    sys.exit(1)

sys.exit(0)
