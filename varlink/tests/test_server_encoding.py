#!/usr/bin/env python

"""Test custom JSON encoding by subclassing VarlinkEncoder and
passing it to a server Service.
"""

import dataclasses
import os
import typing

import varlink
import varlink.error


@dataclasses.dataclass
class Shipment:
    name: str
    description: str
    size: int
    weight: typing.Optional[int] = None


@dataclasses.dataclass
class Order:
    shipments: list[Shipment]
    order_num: int
    customer: str


@dataclasses.dataclass
class GetOrderResult:
    order: Order


class VDCEncoder(varlink.error.VarlinkEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return super().default(obj)


service = varlink.Service(
    vendor="Varlink",
    product="Varlink Encoding Example",
    version="1",
    url="http://varlink.org",
    interface_dir=os.path.dirname(__file__),
    json_encoder_cls=VDCEncoder,
)


class ServiceRequestHandler(varlink.RequestHandler):
    service = service


@service.interface("org.example.encoding")
class EncodingExample:
    sleep_duration = 1

    def Ping(self, ping):
        return {"pong": ping}

    def GetOrder(self, num):
        order = Order(
            shipments=[
                Shipment(
                    name="Furniture",
                    description="Furniture by Ferb",
                    size=1000,
                    weight=400,
                ),
                Shipment(
                    name="Electronics",
                    description="Electronics by Earl",
                    size=588,
                ),
            ],
            order_num=num,
            customer="Joe's Discount Store",
        )
        return GetOrderResult(order=order)


def test_ping(server_factory):
    address = "tcp:127.0.0.1:23451"
    server_factory(address, ServiceRequestHandler)
    client = varlink.Client.new_with_address(address)
    with client.open("org.example.encoding") as conn:
        response = conn.Ping("Foo")
    assert response["pong"] == "Foo"


def test_get_order(server_factory):
    address = "tcp:127.0.0.1:23451"
    server_factory(address, ServiceRequestHandler)

    client = varlink.Client.new_with_address(address)
    with client.open("org.example.encoding") as conn:
        response = conn.GetOrder(4638547)
    # response will be a dict represenation of GetOrderResult
    assert "order" in response
    order = response["order"]
    assert order.get("order_num") == 4638547
    assert order.get("customer") == "Joe's Discount Store"
    assert len(order.get("shipments", [])) == 2
    shipment1 = order["shipments"][0]
    assert shipment1.get("name") == "Furniture"
    assert shipment1.get("weight") is not None
    shipment2 = order["shipments"][1]
    assert shipment2.get("name") == "Electronics"
    assert shipment2.get("weight") is None
