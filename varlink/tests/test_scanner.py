# /usr/bin/env python3

import varlink


def test_scanner_1():
    interface = varlink.Interface("""# Example Varlink service
interface org.example.more

# Enum, returning either start, progress or end
# progress: [0-100]
type State (
  start: ?bool,
  progress: ?int,
  end: ?bool
)

method TestMap(map: [string]string) -> (map: [string](i: int, val: string))

# Returns the same string
method Ping(ping: string) -> (pong: string)

# Dummy progress method
# n: number of progress steps
method TestMore(n: int) -> (state: State)

# Stop serving
method StopServing() -> ()

type ErrorChain (
    description: string,
    caused_by: ?ErrorChain
)

error ActionFailed (reason: ?ErrorChain)

""")
    assert interface.name == "org.example.more"
    assert interface.get_method("Ping") != None
    assert interface.get_method("TestMore") != None
    assert interface.get_method("TestMap") != None
    assert interface.get_method("StopServing") != None
    assert isinstance(interface.members.get("ActionFailed"), varlink._Error)
    assert isinstance(interface.members.get("State"), varlink._Alias)


def test_doubleoption():
    interface = None
    try:
        interface = varlink.Interface("""
interface org.example.doubleoption
method Foo(a: ??string) -> ()
""")
    except SyntaxError:
        pass
    assert interface == None


def test_complex():
    interface = varlink.Interface("""
interface org.example.complex

type TypeEnum ( a, b, c )

type TypeFoo (
    bool: bool,
    int: int,
    float: float,
    string: ?string,
    enum: ?[]( foo, bar, baz ),
    type: ?TypeEnum,
    anon: ( foo: bool, bar: int, baz: [](a: int, b: int) ),
    object: object
)

method Foo(a: (b: bool, c: int), foo: TypeFoo) -> (a: [](b: bool, c: int), foo: TypeFoo)

error ErrorFoo (a: (b: bool, c: int), foo: TypeFoo)
""")
    assert interface.name == "org.example.complex"
    assert interface.get_method("Foo") != None
    assert isinstance(interface.members.get("ErrorFoo"), varlink._Error)
    assert isinstance(interface.members.get("TypeEnum"), varlink._Alias)
