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

    def test_interfacename(self):
        self.assertRaises(SyntaxError, varlink.Interface, "interface .a.b.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface com.-example.leadinghyphen\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface com.example-.danglinghyphen-\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface Com.example.uppercase-toplevel\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface Co9.example.number-toplevel\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface 1om.example.number-toplevel\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface com.Example\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface ab\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface .a.b.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.b.c.\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a..b.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface 1.b.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface 8a.0.0\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface -a.b.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.b.c-\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.b-.c-\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.-b.c-\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.-.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.*.c\nmethod F()->()")
        self.assertRaises(SyntaxError, varlink.Interface, "interface a.?\nmethod F()->()")
        self.assertIsNotNone(varlink.Interface("interface a.b\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a.b.c\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a1.b1.c1\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a1.b--1.c--1\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a--1.b--1.c--1\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a.21.c\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a.1\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface a.0.0\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface org.varlink.service\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface com.example.0example\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface com.example.example-dash\nmethod F()->()").name)
        self.assertIsNotNone(varlink.Interface("interface xn--lgbbat1ad8j.example.algeria\nmethod F()->()").name)
