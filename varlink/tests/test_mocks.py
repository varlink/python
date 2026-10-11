import varlink
from varlink import mock

types = """
type MyPersonalType (
    foo: string,
    bar: string
)
"""


class Service:
    # TODO: these type annotations are wrong as Python type hints, but are used
    # by varlink.mock.generate_callable_interface
    def Test1(self, param1: int) -> str:  # type: ignore
        """return test: MyPersonalType"""
        return {
            "test": {
                "foo": "bim",
                "bar": "boom",
            },
        }  # type: ignore

    def Test2(self, param1: str = "test") -> None:
        pass

    def Test3(self, param1: str) -> str:  # type: ignore
        """return test"""
        return {"test": param1}  # type: ignore


@mock.mockedservice(fake_service=Service, fake_types=types, name="org.service.com", address="unix:@foo")
def test_init():
    with varlink.Client("unix:@foo") as client:
        connection = client.open("org.service.com")
        assert connection.Test1(param1=1)["test"]["bar"] == "boom"
        assert connection.Test3(param1="foo")["test"] == "foo"


def test_cast_type():
    assert mock.cast_type("<class 'int'>") == "int"
    assert mock.cast_type("<class 'str'>") == "string"


def test_get_ignored():
    expected_ignore = dir(mock.MockedService)
    ignored = mock.get_ignored()
    assert expected_ignore == ignored


def test_get_attributs():
    service = Service()
    attributs = mock.get_interface_attributs(service, mock.get_ignored())
    expected_result = {"callables": ["Test1", "Test2", "Test3"], "others": []}
    assert attributs == expected_result


def test_generate_callable_interface():
    service = Service()
    generated_itf = mock.generate_callable_interface(service, "Test1")
    assert generated_itf == "method Test1(param1: int) -> (test: MyPersonalType)"
    generated_itf = mock.generate_callable_interface(service, "Test3")
    assert generated_itf == "method Test3(param1: string) -> (test: string)"
