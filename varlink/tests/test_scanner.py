import pytest

import varlink


def test_scanner_1() -> None:
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
    assert interface.get_method("Ping") is not None
    assert interface.get_method("TestMore") is not None
    assert interface.get_method("TestMap") is not None
    assert interface.get_method("StopServing") is not None
    assert isinstance(interface.members.get("ActionFailed"), varlink.scanner._Error)
    assert isinstance(interface.members.get("State"), varlink.scanner._Alias)


def test_doubleoption() -> None:
    interface = None
    try:
        interface = varlink.Interface("""
    interface org.example.doubleoption
    method Foo(a: ??string) -> ()
    """)
    except SyntaxError:
        pass

    assert interface is None


def test_complex() -> None:
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
    assert interface.get_method("Foo") is not None
    assert isinstance(interface.members.get("ErrorFoo"), varlink.scanner._Error)
    assert isinstance(interface.members.get("TypeEnum"), varlink.scanner._Alias)


invalid_interfacenames = [
    "interface .a.b.c\nmethod F()->()",
    "interface com.-example.leadinghyphen\nmethod F()->()",
    "interface com.example-.danglinghyphen-\nmethod F()->()",
    "interface co9.example.number-toplevel\nmethod F()->()",
    "interface 1om.example.number-toplevel\nmethod F()->()",
    "interface ab\nmethod F()->()",
    "interface .a.b.c\nmethod F()->()",
    "interface a.b.c.\nmethod F()->()",
    "interface a..b.c\nmethod F()->()",
    "interface 1.b.c\nmethod F()->()",
    "interface 8a.0.0\nmethod F()->()",
    "interface -a.b.c\nmethod F()->()",
    "interface a.b.c-\nmethod F()->()",
    "interface a.b-.c-\nmethod F()->()",
    "interface a.-b.c-\nmethod F()->()",
    "interface a.-.c\nmethod F()->()",
    "interface a.*.c\nmethod F()->()",
    "interface a.?\nmethod F()->()",
]


@pytest.mark.parametrize("description", invalid_interfacenames)
def test_interfacename_invalid(description) -> None:
    with pytest.raises(SyntaxError):
        varlink.Interface(description)


valid_interfacenames = [
    "interface a.b\nmethod F()->()",
    "interface a.b.c\nmethod F()->()",
    "interface a.1\nmethod F()->()",
    "interface a.0.0\nmethod F()->()",
    "interface org.varlink.service\nmethod F()->()",
    "interface com.example.0example\nmethod F()->()",
    "interface com.example.example-dash\nmethod F()->()",
    "interface xn--lgbbat1ad8j.example.algeria\nmethod F()->()",
    "interface xn--c1yn36f.xn--c1yn36f.xn--c1yn36f\nmethod F()->()",
]


@pytest.mark.parametrize("description", valid_interfacenames)
def test_interfacename_valid(description) -> None:
    assert varlink.Interface(description).name is not None


def test_bad_types() -> None:
    interface = varlink.Interface("""
    interface org.example.testerrors
    type TypeEnum ( a, b, c )
    type TypeDict (dict: [string]string)

    method Foo(param: TypeEnum) -> ()
    method Bar(param: TypeDict) -> ()
    """)
    foo = interface.get_method("Foo")
    with pytest.raises(varlink.InvalidParameter):
        interface.filter_params("test.call", foo.in_type, False, (), {"param": "d"})

    bar = interface.get_method("Bar")
    with pytest.raises(varlink.InvalidParameter):
        interface.filter_params("test.call", bar.in_type, False, (), {"param": {"dict": [1, 2, 3]}})


def test_method_not_found() -> None:
    interface = varlink.Interface("""
    interface org.example.testerrors
    """)

    with pytest.raises(varlink.MethodNotFound):
        interface.get_method("Bar")


def test_struct_errors() -> None:
    missing_colon_after_name = """
    interface org.example.teststruct

    type TypeStruct ( struct ?[](first: int, second: string) )
    """

    with pytest.raises(SyntaxError, match="after 'struct'"):
        varlink.Interface(missing_colon_after_name)

    missing_colon_in_struct = """
    interface org.example.teststruct

    type MyType (
        nullable_array_struct: ?[](first: int, second string)
    )
    method Start() -> (client_id: string)
    """
    with pytest.raises(SyntaxError, match="after 'second'"):
        varlink.Interface(missing_colon_in_struct)


def test_unexpected() -> None:
    invalid = """
    interface org.example.unexpected

    invalid
    """

    with pytest.raises(SyntaxError, match="expected type, method, or error"):
        varlink.Interface(invalid)
