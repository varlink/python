import threading

import pytest

import varlink


class ServiceRequestHandler(varlink.RequestHandler): ...


@pytest.fixture
def server_factory():
    servers = []

    def _create_server(address: str, service: varlink.Service):
        ServiceRequestHandler.service = service
        server = varlink.ThreadingServer(address, ServiceRequestHandler)
        ready_event = threading.Event()

        def run_server() -> None:
            ready_event.set()
            server.serve_forever()

        server_thread = threading.Thread(target=run_server)
        server_thread.start()
        ready_event.wait()
        servers.append((server, server_thread))

        return server

    yield _create_server

    for srv, srv_thread in servers:
        srv.shutdown()
        srv.server_close()
        srv_thread.join()
