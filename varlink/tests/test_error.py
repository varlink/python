import json
import unittest

import varlink


class OneMessageClientHandler(varlink.ClientInterfaceHandler):
    def __init__(self, interface, namespaced, next_message):
        # No interface but we do not use them
        super().__init__(interface, namespaced)
        self.next_message = next_message

    def _next_message(self):
        yield self.next_message


class TestError(unittest.TestCase):
    def test_pack_unpack(self):
        dummy_if = varlink.Interface("interface org.example.dummy")
        for error in [
            varlink.InterfaceNotFound("org.varlink.notfound"),
            varlink.MethodNotImplemented("Abstract"),
            varlink.InvalidParameter("Struct.param"),
        ]:
            for namespaced in (True, False):
                with self.subTest(error=error, namespaced=namespaced):
                    # encode error
                    encoded = json.dumps(error, cls=varlink.VarlinkEncoder)

                    # Emulates the client receiving an error
                    handler = OneMessageClientHandler(dummy_if, namespaced, encoded)
                    with self.assertRaises(error.__class__):
                        handler._next_varlink_message()
