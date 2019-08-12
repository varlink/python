import time
import unittest
from varlink import mock
import varlink


types = """
type MyPersonalType (
    foo: string,
    bar: string
)
"""


class Service():

    def Test1(self, param1: int) -> str:
        """return test: MyPersonalType"""
        return {
            "test": {
                "foo": "bim",
                "bar": "boom"
            }
        }

    def Test2(self, param1: str="test") -> None:
        pass

    def Test3(self, param1: str) -> str:
        """return test"""
        return {"test": param1}


class TestMockMechanisms(unittest.TestCase):

    @mock.mockedservice(
        fake_service=Service,
        fake_types=types,
        name='org.service.com',
        address='unix:@foo'
    )
    def test_init(self):
        with varlink.Client("unix:@foo") as client:
            connection = client.open('org.service.com')
            self.assertEqual(connection.Test1(param1=1)["test"]["bar"], "boom")
            self.assertEqual(connection.Test3(param1="foo")["test"], "foo")


class TestMockUtilities(unittest.TestCase):

    def test_cast_type(self):
        self.assertEqual(mock.cast_type("<class 'int'>"), 'int')
        self.assertEqual(mock.cast_type("<class 'str'>"), 'string')

    def test_get_ignored(self):
        expected_ignore = dir(mock.MockedService)
        ignored = mock.get_ignored()
        self.assertEqual(expected_ignore, ignored)

    def test_get_attributs(self):
        service = Service()
        attributs = mock.get_interface_attributs(service, mock.get_ignored())
        expected_result = {
            "callables": ["Test1", "Test2", "Test3"],
            "others": []
        }
        self.assertEqual(attributs, expected_result)

    def test_generate_callable_interface(self):
        service = Service()
        generated_itf = mock.generate_callable_interface(service, 'Test1')
        self.assertEqual(
            generated_itf,
            "method Test1(param1: int) -> (test: MyPersonalType)")
        generated_itf = mock.generate_callable_interface(service, 'Test3')
        self.assertEqual(
            generated_itf,
            "method Test3(param1: string) -> (test: string)")
