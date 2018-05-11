[![Build Status](https://travis-ci.org/varlink/python.svg?branch=master)](https://travis-ci.org/varlink/python)
[![Coverage Status](https://coveralls.io/repos/github/varlink/python/badge.svg?branch=master)](https://coveralls.io/github/varlink/python?branch=master)
[![Varlink Certified](https://img.shields.io/badge/varlink-certified-green.svg)](https://www.varlink.org/Language-Bindings)

# python-varlink

A [varlink](http://varlink.org) implementation for Python.

* [GIT Repository](https://github.com/varlink/python)
* [API documentation](https://varlink.github.io/python/)

## python varlink installation

From pypi:
```bash
$ pip3 install --user varlink
```

With Fedora 28/rawhide:
```bash
$ sudo dnf install python3-varlink
```

## Examples

See the [tests](https://github.com/varlink/python-varlink/tree/master/varlink/tests) directory.

```bash
$ python3 -m varlink.tests.test_orgexamplemore --varlink="unix:/tmp/test" &
[1] 6434
$ python -m varlink.cli help unix:/tmp/test/org.example.more
# Example Varlink service
interface org.example.more

# Enum, returning either start, progress or end
# progress: [0-100]
type State (
  start: ?bool,
  progress: ?int,
  end: ?bool
)

# Returns the same string
method Ping(ping: string) -> (pong: string)

# Dummy progress method
# n: number of progress steps
method TestMore(n: int) -> (state: State)

# Stop serving
method StopServing() -> ()

# Something failed in TestMore
error TestMoreError (reason: string)


$ fg
python3 -m varlink.tests.test_orgexamplemore --varlink="unix:/tmp/test"
^C
```

```bash
$ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py
Connecting to exec:./varlink/tests/test_orgexamplemore

Listening on @0002c
Ping:  Test
--- Start ---
Progress: 0
Progress: 10
Progress: 20
Progress: 30
Progress: 40
Progress: 50
Progress: 60
Ping:  Test
Progress: 70
Ping:  Test
Progress: 80
Ping:  Test
Progress: 90
Ping:  Test
Progress: 100
Ping:  Test
--- End ---
```

```bash
$ python3 -m varlink.tests.test_orgexamplemore --varlink="unix:/tmp/test" &
Listening on /tmp/test
[1] 6434
python3 -m varlink.tests.test_orgexamplemore --client --varlink="unix:/tmp/test"
Connecting to unix:/tmp/test

Ping:  Test
--- Start ---
Progress: 0
Progress: 10
Progress: 20
Progress: 30
Progress: 40
Progress: 50
Progress: 60
Ping:  Test
Progress: 70
Ping:  Test
Progress: 80
Ping:  Test
Progress: 90
Ping:  Test
Progress: 100
Ping:  Test
--- End ---

$ python3 -m varlink.cli call --more unix:/tmp/test/org.example.more.TestMore '{ "n": 10 }'
{'state': {'start': True}}
{'state': {'progress': 0}}
{'state': {'progress': 10}}
{'state': {'progress': 20}}
{'state': {'progress': 30}}
{'state': {'progress': 40}}
{'state': {'progress': 50}}
{'state': {'progress': 60}}
{'state': {'progress': 70}}
{'state': {'progress': 80}}
{'state': {'progress': 90}}
{'state': {'progress': 100}}
{'state': {'end': True}}

$ fg
python3 -m varlink.tests.test_orgexamplemore --varlink="unix:/tmp/test"
^C
```

You can also start the clients and server with URLs following the [varlink URL standard](https://github.com/varlink/documentation/wiki#address).
E.g.
- unix:@anonuds
- unix:/run/myserver/socketfile
- tcp:127.0.0.1:12345
- tcp:[::1]:12345

### Varlink Certification Server

```
$ python3 -m varlink.tests.test_certification --varlink=tcp:127.0.0.1:12345
```

### Varlink Certification Client

```
$ python3 -m varlink.tests.test_certification --varlink=tcp:127.0.0.1:12345 --client
```
