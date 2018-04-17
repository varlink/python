import json
import math
import os
import sys

import varlink

service = varlink.Service(
    vendor='Varlink',
    product='Varlink Examples',
    version='1',
    url='http://varlink.org',
    interface_dir=os.path.dirname(__file__)
)


class ServiceRequestHandler(varlink.RequestHandler):
    service = service


def sorted_json(dct):
    if isinstance(dct, type([])):
        return sorted(dct)
    return dct

class CertificationError(varlink.VarlinkError):

    def __init__(self, wants, got):
        varlink.VarlinkError.__init__(self,
                                      {'error': 'org.varlink.certification.CertificationError',
                                       'parameters': {'wants': wants, 'got': got}})


@service.interface('org.varlink.certification')
class CertService:
    def assert_raw(self, _raw, _message, wants):

        have = json.loads(wants, object_hook=sorted_json)

        if have != _message:
            raise CertificationError(wants, _raw.decode("utf-8"))

    def assert_cmp(self, _raw, wants, _bool):
        if not _bool:
            raise CertificationError(wants, _raw.decode("utf-8"))

    def Start(self, _raw=None, _message=None):
        self.assert_raw(_raw, _message, '{"method": "org.varlink.certification.Start", "parameters": {}}')

    # () -> (bool: bool)
    def Test01(self, _raw=None, _message=None):
        self.assert_raw(_raw, _message, '{"method": "org.varlink.certification.Test01", "parameters": {}}')
        return {"bool": True}

    # (bool: bool) -> (int: int)
    def Test02(self, _bool, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test02", "parameters": {"bool": true}}'
        self.assert_cmp(_raw, wants, _bool == True)
        self.assert_raw(_raw, _message, wants)
        return {"int": 1}

    # (int: int) -> (float: float)
    def Test03(self, _int, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test03", "parameters": {"int": 1}}'
        self.assert_cmp(_raw, wants, _int == 1)
        self.assert_raw(_raw, _message, wants)
        return {"float": 1.0}

    # (float: float) -> (string: string)
    def Test04(self, _float, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test04", "parameters": {"float": 1.0}}'
        self.assert_cmp(_raw, wants, _float == 1.0)
        self.assert_raw(_raw, _message, wants)
        return {"string": "ping"}

    # (string: string) -> (bool: bool, int: int, float: float, string: string)
    def Test05(self, _string, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test05", "parameters": {"string": "ping"}}'
        self.assert_cmp(_raw, wants, _string == "ping")
        self.assert_raw(_raw, _message, wants)
        return {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}

    # (bool: bool, int: int, float: float, string: string)
    # -> (struct: (bool: bool, int: int, float: float, string: string))
    def Test06(self, _bool, _int, _float, _string, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test06", "parameters": ' \
                '{"bool": false, "int": 2, "float": ' + str(math.pi) + ', "string": "a lot of ' \
                'string"}}'
        self.assert_raw(_raw, _message, wants)
        self.assert_cmp(_raw, wants, _int == 2)
        self.assert_cmp(_raw, wants, _bool == False)
        self.assert_cmp(_raw, wants, _float == math.pi)
        self.assert_cmp(_raw, wants, _string == "a lot of string")

        return {"struct": {"bool": False, "int": 2, "float": math.pi, "string": "a lot of string"}}

    # (struct: (bool: bool, int: int, float: float, string: string)) -> (map: [string]string)
    def Test07(self, _dict, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test07", "parameters": ' \
                '{"struct": {"int": 2, "bool": false, "float": ' + str(math.pi) + ', "string": "a lot of ' \
                'string"}}}'
        self.assert_raw(_raw, _message, wants)
        self.assert_cmp(_raw, wants, _dict["int"] == 2)
        self.assert_cmp(_raw, wants, _dict["bool"] == False)
        self.assert_cmp(_raw, wants, _dict["float"] == math.pi)
        self.assert_cmp(_raw, wants, _dict["string"] == "a lot of string")
        return {"map": {"foo": "Foo", "bar": "Bar"}}

    # (map: [string]string) -> (set: [string]())
    def Test08(self, _map, _raw=None, _message=None):
        self.assert_raw(_raw, _message,
                        '{"method": "org.varlink.certification.Test08", "parameters": {"map" : {"foo": "Foo", '
                        '"bar": "Bar"}}}')
        return {"set": {"one", "two", "three"}}

    # (set: [string]()) -> (mytype: MyType)
    def Test09(self, _set, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.Test09", "parameters": {"set" : {"one": {}, "three": {},' \
                ' "two": {}}}}'
        self.assert_raw(_raw, _message, wants)
        self.assert_cmp(_raw, wants, isinstance(_set, set))
        self.assert_cmp(_raw, wants, len(_set) == 3)
        self.assert_cmp(_raw, wants, "one" in _set)
        self.assert_cmp(_raw, wants, "two" in _set)
        self.assert_cmp(_raw, wants, "three" in _set)
        return {"mytype": {
            "object": {"method": "org.varlink.certification.Test09",
                       "parameters": {"map": {"foo": "Foo", "bar": "Bar"}}},
            "enum": "two",
            "struct": {"first": 1, "second": "2"},
            "array": ["one", "two", "three"],
            "dictionary": {"foo": "Foo", "bar": "Bar"},
            "stringset": {"one", "two", "three"},
            "nullable": None,
            "nullable_array_struct": None,
            "interface": {
                "foo": [
                    None,
                    {"foo": "foo", "bar": "bar"},
                    None,
                    {"one": "foo", "two": "bar"}
                ],
                "anon": {"foo": True, "bar": False}
            }
        }}

    # (mytype: MyType) -> ()
    def End(self, mytype, _raw=None, _message=None):
        wants = '{"method": "org.varlink.certification.End", "parameters": {"mytype": {"object": {"method": ' \
                '"org.varlink.certification.Test09", "parameters": ' \
                '{"map": {"foo": "Foo", "bar": "Bar"}}}, "enum": "two", "struct": {"first": 1, "second": "2"}, ' \
                '"array": ["one", "two", "three"], "dictionary": {"foo": "Foo", "bar": "Bar"}, "stringset": ' \
                '{"two": {}, "one": {}, "three": {}}, ' \
                '"interface": {"foo": [null, {"foo": "foo", "bar": "bar"}, null, {"one": "foo", "two": "bar"}], ' \
                '"anon": {"foo": true, "bar": false}}}}}'

        if "nullable" in mytype:
            self.assert_cmp(_raw, wants, mytype["nullable"] == None)
            del mytype["nullable"]

        if "nullable_array_struct" in mytype:
            self.assert_cmp(_raw, wants, mytype["nullable_array_struct"] == None)
            del mytype["nullable_array_struct"]

        self.assert_cmp(_raw, wants, mytype == {
            "object": {"method": "org.varlink.certification.Test09",
                       "parameters": {"map": {"foo": "Foo", "bar": "Bar"}}},
            "enum": "two",
            "struct": {"first": 1, "second": "2"},
            "array": ["one", "two", "three"],
            "dictionary": {"foo": "Foo", "bar": "Bar"},
            "stringset": {"one", "two", "three"},
            "interface": {
                "foo": [
                    None,
                    {"foo": "foo", "bar": "bar"},
                    None,
                    {"one": "foo", "two": "bar"}
                ],
                "anon": {"foo": True, "bar": False}
            }
        })
        self.assert_raw(_raw, _message, wants)


if __name__ == '__main__':
    if len(sys.argv) < 2 or not sys.argv[1].startswith("--varlink="):
        print('Usage: %s --varlink=<varlink address>' % sys.argv[0])
        sys.exit(1)

    with varlink.ThreadingServer(sys.argv[1][10:], ServiceRequestHandler) as server:
        print("Listening on", server.server_address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    sys.exit(0)
