from __future__ import print_function
from __future__ import unicode_literals

import unittest

import varlink


class TestScanner(unittest.TestCase):
    def test_scanner_1(self):
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
        self.assertEqual(interface.name, "org.example.more")
        self.assertIsNotNone(interface.get_method("Ping"))
        self.assertIsNotNone(interface.get_method("TestMore"))
        self.assertIsNotNone(interface.get_method("TestMap"))
        self.assertIsNotNone(interface.get_method("StopServing"))
        self.assertIsInstance(interface.members.get("ActionFailed"), varlink.scanner._Error)
        self.assertIsInstance(interface.members.get("State"), varlink.scanner._Alias)

    def test_doubleoption(self):
        interface = None
        try:
            interface = varlink.Interface("""
    interface org.example.doubleoption
    method Foo(a: ??string) -> ()
    """)
        except SyntaxError:
            pass

        self.assertIsNone(interface)

    def test_complex(self):
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
        self.assertEqual(interface.name, "org.example.complex")
        self.assertIsNotNone(interface.get_method("Foo"))
        self.assertIsInstance(interface.members.get("ErrorFoo"), varlink.scanner._Error)
        self.assertIsInstance(interface.members.get("TypeEnum"), varlink.scanner._Alias)
