import os
import socket
import sys
import threading

import pytest

import varlink

service = varlink.Service(
    vendor="Varlink",
    product="Varlink Examples",
    version="1",
    url="http://varlink.org",
    interface_dir=os.path.dirname(__file__),
)


test_addresses = [
    ("tcp:127.0.0.1:23450", False, ""),
    (
        f"unix:@org.varlink.service_anon_test{os.getpid()}{threading.current_thread().name}",
        not sys.platform.startswith("linux"),
        "Only runs on Linux",
    ),
    (
        f"unix:org.varlink.service_anon_test_{os.getpid()}{threading.current_thread().name}",
        not hasattr(socket, "AF_UNIX"),
        "No UNIX socket support",
    ),
]


@pytest.mark.parametrize("address,skip,skip_reason", test_addresses)
def test_address(server_factory, address, skip, skip_reason) -> None:
    if skip:
        pytest.skip(skip_reason)

    server_factory(address, service)

    with varlink.Client(address) as client, client.open("org.varlink.service") as connection:
        info = connection.GetInfo()

        assert len(info["interfaces"]) == 1
        assert info["interfaces"][0] == "org.varlink.service"
        assert info == service.GetInfo()

        desc = connection.GetInterfaceDescription(info["interfaces"][0])
        assert desc == service.GetInterfaceDescription("org.varlink.service")

        connection.close()


def test_reuse_open(server_factory) -> None:
    address = "tcp:127.0.0.1:23450"
    server_factory(address, service)

    with varlink.Client(address) as client:
        connection = client.open_connection()
        re_use = client.open("org.varlink.service", False, connection)
        info = re_use.GetInfo()

        assert len(info["interfaces"]) == 1
        assert info["interfaces"][0] == "org.varlink.service"
        assert info == service.GetInfo()
        connection.close()


def test_wrong_url(server_factory) -> None:
    address = f"uenix:org.varlink.service_wrong_url_test_{os.getpid()}"
    with pytest.raises(ConnectionError):
        server_factory(address, service)
