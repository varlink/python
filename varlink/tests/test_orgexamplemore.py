#!/usr/bin/env python

"""Server and Client example of varlink for python

From the main git repository directory run::

    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py

or::

    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py --varlink="unix:@test" &
    Listening on @test
    [1] 6434
    $ PYTHONPATH=$(pwd) python3 ./varlink/tests/test_orgexamplemore.py --client --varlink="unix:@test"
    [...]

"""

import argparse
import os
import shlex
import socket
import sys
import textwrap
import time
from sys import platform

import pytest

import varlink

######## CLIENT #############


def run_client(client):
    print(f"Connecting to {client}\n")
    try:
        with (
            client.open("org.example.more", namespaced=True) as con1,
            client.open("org.example.more", namespaced=True) as con2,
        ):
            for m in con1.TestMore(10, _more=True):
                if hasattr(m.state, "start") and m.state.start is not None:
                    if m.state.start:
                        print("--- Start ---", file=sys.stderr)

                if hasattr(m.state, "end") and m.state.end is not None:
                    if m.state.end:
                        print("--- End ---", file=sys.stderr)

                if hasattr(m.state, "progress") and m.state.progress is not None:
                    print("Progress:", m.state.progress, file=sys.stderr)
                    if m.state.progress > 50:
                        ret = con2.Ping("Test")
                        print("Ping: ", ret.pong)

    except ConnectionError as e:
        print("ConnectionError:", e)
        raise e
    except varlink.VarlinkError as e:
        print(e)
        print(e.error())
        print(e.parameters())
        raise e


######## SERVER #############

service = varlink.Service(
    vendor="Varlink",
    product="Varlink Examples",
    version="1",
    url="http://varlink.org",
    interface_dir=os.path.dirname(__file__),
)


class ActionFailed(varlink.VarlinkError):
    def __init__(self, reason):
        varlink.VarlinkError.__init__(
            self, {"error": "org.example.more.ActionFailed", "parameters": {"field": reason}}
        )


@service.interface("org.example.more")
class Example:
    sleep_duration = 1.0

    def TestMore(self, n, _more=True, _server=None):
        try:
            if not _more:
                yield varlink.InvalidParameter("more")

            yield {"state": {"start": True}, "_continues": True}

            for i in range(0, n):
                yield {"state": {"progress": int(i * 100 / n)}, "_continues": True}
                time.sleep(self.sleep_duration)

            yield {"state": {"progress": 100}, "_continues": True}

            yield {"state": {"end": True}, "_continues": False}
        except Exception as error:
            print("ERROR", error, file=sys.stderr)
            if _server:
                _server.shutdown()

    def Ping(self, ping):
        return {"pong": ping}

    def StopServing(self, reason=None, _request=None, _server=None):
        print("Server ends.")

        if _request:
            print("Shutting down client connection")
            _server.shutdown_request(_request)

        if _server:
            print("Shutting down server")
            _server.shutdown()

    def TestMap(self, map):
        i = 1
        ret = {}
        for key, val in map.items():
            ret[key] = {"i": i, "val": val}
            i += 1
        return {"map": ret}

    def TestObject(self, object):
        import json

        return {"object": json.loads(json.dumps(object))}


def run_server(address):
    with varlink.ThreadingServer(address, service) as server:
        print("Listening on", server.server_address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


######## MAIN #############


def epilog():
    arg0 = sys.argv[0]
    return textwrap.dedent(
        f"""
    Examples:
        \tSelf Exec: $ {arg0}
        \tServer   : $ {arg0} --varlink=<varlink address>
        \tClient   : $ {arg0} --client --varlink=<varlink address>
        \tClient   : $ {arg0} --client --bridge=<bridge command>
        \tClient   : $ {arg0} --client --activate=<activation command>
    """
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Varlink org.example.more test case",
        epilog=epilog(),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--varlink", type=str, help="The varlink address")
    parser.add_argument("-b", "--bridge", type=str, help="bridge command")
    parser.add_argument("-A", "--activate", type=str, help="activation command")
    parser.add_argument("--client", action="store_true", help="launch the client mode")
    args = parser.parse_args()

    address = args.varlink
    client_mode = args.client
    activate = args.activate
    bridge = args.bridge

    client = None

    if client_mode:
        if bridge:
            client = varlink.Client.new_with_bridge(shlex.split(bridge))
        if activate:
            client = varlink.Client.new_with_activate(shlex.split(activate))
        if address:
            client = varlink.Client.new_with_address(address)

    if not address and not client_mode:
        if not hasattr(socket, "AF_UNIX"):
            print(f"varlink activate: not supported on platform {platform}", file=sys.stderr)
            parser.print_help()
            sys.exit(2)

        client_mode = True
        with varlink.Client.new_with_activate([__file__, "--varlink=$VARLINK_ADDRESS"]) as client:
            run_client(client)
    elif client_mode:
        if client is None:
            raise ValueError("--client requires at either of --varlink, --bridge or --activate")
        with client:
            run_client(client)
    else:
        run_server(address)

    sys.exit(0)


######## UNITTEST #############


def test_service(server_factory) -> None:
    address = "tcp:127.0.0.1:23451"
    Example.sleep_duration = 0.1
    server_factory(address, service)

    client = varlink.Client.new_with_address(address)

    run_client(client)

    with (
        client.open("org.example.more", namespaced=True) as con1,
        client.open("org.example.more", namespaced=True) as con2,
    ):
        assert con1.Ping("Test").pong == "Test"

        it = con1.TestMore(10, _more=True)

        m = next(it)
        assert hasattr(m.state, "start")
        assert not hasattr(m.state, "end")
        assert not hasattr(m.state, "progress")
        assert m.state.start is not None

        for i in range(0, 110, 10):
            m = next(it)
            assert hasattr(m.state, "progress")
            assert not hasattr(m.state, "start")
            assert not hasattr(m.state, "end")
            assert m.state.progress is not None
            assert i == m.state.progress

            if i > 50:
                ret = con2.Ping("Test")
                assert ret.pong == "Test"

        m = next(it)
        assert hasattr(m.state, "end")
        assert not hasattr(m.state, "start")
        assert not hasattr(m.state, "progress")
        assert m.state.end is not None

        with pytest.raises(StopIteration):
            next(it)

        con1.StopServing(_oneway=True)
        time.sleep(0.5)

        with pytest.raises(ConnectionError):
            con1.Ping("Test")
