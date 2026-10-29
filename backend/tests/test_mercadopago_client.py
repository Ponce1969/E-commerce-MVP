import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from src.infrastructure.payments.mercadopago_client import MercadoPagoClient


class DummyItem:
    def __init__(self, product_id: int, name: str, quantity: int, unit_price: Decimal):
        self.product_id = product_id
        self.product = DummyProduct(name)
        self.quantity = quantity
        self.unit_price = unit_price


class DummyProduct:
    def __init__(self, name: str):
        self.name = name


class DummyOrder:
    def __init__(self, order_id: int, delivery_cost: Decimal = Decimal("250.00")):
        self.id = order_id
        self.delivery_cost = delivery_cost
        self.preference_id: str | None = None


@pytest.mark.asyncio
async def test_crear_preferencia_success() -> None:
    captured_payload: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        if request.url.path == "/checkout/preferences":
            await request.aread()
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                201,
                json={
                    "id": "PREF-123456",
                    "init_point": "https://www.mercadopago.com.uy/checkout/v1/redirect?pref_id=PREF-123456",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = MercadoPagoClient(access_token="TEST_TOKEN", transport=transport)
    order = DummyOrder(order_id=42, delivery_cost=Decimal("250.00"))
    items = [
        DummyItem(
            product_id=1,
            name="Detergente Moizo 5L",
            quantity=2,
            unit_price=Decimal("450.00"),
        )
    ]

    init_point = await client.crear_preferencia(order=order, items=items)

    assert init_point == "https://www.mercadopago.com.uy/checkout/v1/redirect?pref_id=PREF-123456"
    assert order.preference_id == "PREF-123456"
    assert captured_payload["external_reference"] == "42"
    assert captured_payload["auto_return"] == "approved"
    assert len(captured_payload["items"]) == 2
    assert captured_payload["items"][0]["title"] == "Detergente Moizo 5L"
    assert captured_payload["items"][0]["unit_price"] == 450.0
    assert captured_payload["items"][0]["currency_id"] == "UYU"
    assert captured_payload["items"][1]["id"] == "shipping_fee"
    assert captured_payload["items"][1]["unit_price"] == 250.0


@pytest.mark.asyncio
async def test_obtener_pago_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/payments/999888777":
            return httpx.Response(
                200,
                json={
                    "id": 999888777,
                    "status": "approved",
                    "external_reference": "42",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = MercadoPagoClient(access_token="TEST_TOKEN", transport=transport)

    data = await client.obtener_pago("999888777")
    assert data["id"] == 999888777
    assert data["status"] == "approved"
    assert data["external_reference"] == "42"
