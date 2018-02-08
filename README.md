# python-varlink

A [varlink](http://varlink.org) implementation for Python.

## varlink tool installation

With Fedora 28/rawhide:
```bash
$ sudo dnf install python-varlink libvarlink-util
```

## Examples

See the [examples](https://github.com/varlink/python-varlink/tree/master/examples) directory.

```bash
$ python3 server-simple.py 'unix:/tmp/tt;mode=0666' &
[1] 6434
$ varlink help unix:/tmp/tt/org.varlink.example.more
# Example Varlink service
interface org.varlink.example.more

# Enum, returning either start, progress or end
# progress: [0-100]
type State (
  start: bool,
  progress: int,
  end: bool
)

# Returns the same string
method Ping(ping: string) -> (pong: string)

# Dummy progress method
# n: number of progress steps
method TestMore(n: int) -> (state: State)

# Something failed
error ActionFailed (reason: string)

$ fg
python3 server-simple.py 'unix:/tmp/tt;mode=0666'
^CTraceback (most recent call last):
  File "server-simple.py", line 56, in <module>
    s.serve(sys.argv[1], listen_fd=listen_fd)
  File "/home/harald/git/varlink/python-varlink/varlink/__init__.py", line 871, in serve
    for fd, events in epoll.poll():
KeyboardInterrupt
```

```bash
$ python3 server-twisted.py 'unix:/tmp/tt;mode=0666' &
$ varlink help unix:/tmp/tt/org.varlink.example.more
# Example Varlink service
interface org.varlink.example.more

# Enum, returning either start, progress or end
# progress: [0-100]
type State (
  start: bool,
  progress: int,
  end: bool
)

# Returns the same string
method Ping(ping: string) -> (pong: string)

# Dummy progress method
# n: number of progress steps
method TestMore(n: int) -> (state: State)

# Something failed
error ActionFailed (reason: string)
$ kill %1
```

```bash
$ python3 client-simple.py 
Connecting to exec:./server-simple.py

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
$ python3 client-twisted.py 
Connecting to exec:./server-twisted.py

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

