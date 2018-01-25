# python-varlink

A [varlink](http://varlink.org) implementation for Python.

## varlink tool installation

```bash
$ sudo dnf copr enable "@varlink/varlink"
$ sudo dnf install fedora-varlink
$ sudo setenforce 0 # needed until systemd is able to create sockets in /run
$ sudo systemctl enable --now org.varlink.resolver.socket
$ varlink help
```

## python client example usage

```python
from varlink import Client    
iface = Client(interface='io.systemd.journal')["io.systemd.journal"]

iface.Monitor(initial_lines=1)

for m in iface.Monitor(initial_lines=10, _more=True):
    for e in m.entries:
        print("%s: %s" % (e.time, e.message))
```

## python server example
See https://github.com/varlink/com.redhat.system/blob/master/accounts/accounts.py
