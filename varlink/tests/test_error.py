import json

import pytest

import varlink


class OneMessageClientHandler(varlink.ClientInterfaceHandler):
    def __init__(self, interface, namespaced, next_message):
        # No interface but we do not use them
        super().__init__(interface, namespaced)
        self.next_message = next_message

    def _next_message(self):
        yield self.next_message


@pytest.mark.parametrize(
    "error",
    [
        varlink.InterfaceNotFound("org.varlink.notfound"),
        varlink.MethodNotFound("Method"),
        varlink.MethodNotImplemented("Abstract"),
        varlink.InvalidParameter("Struct.param"),
    ],
)
@pytest.mark.parametrize("namespaced", [True, False])
def test_pack_unpack(error, namespaced):
    dummy_if = varlink.Interface("interface org.example.dummy")

    # encode error
    encoded = json.dumps(error, cls=varlink.VarlinkEncoder)

    # Emulates the client receiving an error
    handler = OneMessageClientHandler(dummy_if, namespaced, encoded)
    with pytest.raises(error.__class__):
        handler._next_varlink_message()
