#!/usr/bin/env python3

import sys

from varlink import (Client, VarlinkError)

if len(sys.argv) == 2:
    address = sys.argv[1]
else:
    address = 'exec:./server-simple.py'

print('Connecting to %s\n' % address)
try:
    with Client(address=address) as client, \
            client.open('org.example.more', namespaced=True) as con1, \
            client.open('org.example.more', namespaced=True) as con2:
        for m in con1.TestMore(10, _more=True):
            if hasattr(m.state, 'start') and m.state.start:
                print("--- Start ---", file=sys.stderr)

            elif hasattr(m.state, 'end') and m.state.end:
                print("--- End ---", file=sys.stderr)

            elif hasattr(m.state, 'progress'):
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
