import json
from typing import Any

import httpx
import pytest

from src.infrastructure.logistics.marco_postal_client import MarcoPostalClient


class DummyProduct:
    def __init__(self, name: str):
        self.name = name


class DummyItem:
    def __init__(self, product_id: int, name: str, quantity: int):
        self.product_id = product_id
        self.product = DummyProduct(name)
        self.quantity = quantity


class DummyOrder:
    def __init__(self, order_id: int):
        self.id = order_id
        self.shipping_recipient_name = "Juan Pérez"
        self.shipping_document_number = "41234567"
        self.shipping_street = "Av. 18 de Julio"
        self.shipping_street_number = "1234"
        self.shipping_apartment = "Apto 502"
        self.shipping_city = "Montevideo"
        self.shipping_state = "Montevideo"
        self.shipping_postal_code = "11200"
        self.shipping_phone = "099112233"
        self.shipping_notes = "Dejar en portería"
        self.delivery_notes = None
        self.items = [DummyItem(1, "Lavandina 5L", 2)]
        self.remito_postal: str | None = None
        self.tracking_url: str | None = None


@pytest.mark.asyncio
async def test_crear_guia_success() -> None:
    captured_payload: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        if request.url.path == "/api/v2/guias.json":
            await request.aread()
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "remito": "2R-55",
                    "tracking_url": "https://marcopostal.epresis.com/seguimiento/2R-55",
                    "constancia": "https://marcopostal.epresis.com/constancia/2R-55.pdf",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = MarcoPostalClient(
        api_url="https://marcopostal.epresis.com/api/v2",
        token="MOCK_TOKEN",
        sucursal="10090",
        servicio="004",
        transport=transport,
    )
    order = DummyOrder(order_id=55)

    result = await client.crear_guia(order=order)

    assert result["status"] == "success"
    assert order.remito_postal == "2R-55"
    assert order.tracking_url == "https://marcopostal.epresis.com/seguimiento/2R-55"

    assert captured_payload["remito"] == "2R-55"
    assert captured_payload["sucursal"] == "10090"
    assert captured_payload["servicio"] == "004"
    assert (
        captured_payload["remitente"]["empresa"]
        == "Dos Rodríguez Distribuidora - Mariana Moreira Rodríguez"
    )
    assert captured_payload["remitente"]["rut"] == "220848220010"

    comprador = captured_payload["comprador"]
    assert comprador["destinatario"] == "Juan Pérez"
    assert comprador["documento"] == "41234567"
    assert comprador["calle"] == "Av. 18 de Julio"
    assert comprador["altura"] == "1234"
    assert comprador["piso"] == "Apto 502"
    assert comprador["localidad"] == "Montevideo"
    assert comprador["provincia"] == "Montevideo"
    assert comprador["cp"] == "11200"
    assert comprador["celular"] == "099112233"
    assert comprador["observaciones"] == "Dejar en portería"

    assert len(captured_payload["productos"]) == 1
    assert captured_payload["productos"][0]["descripcion"] == "Lavandina 5L"
    assert captured_payload["productos"][0]["cantidad"] == 2
    assert captured_payload["bultos"] == 1


@pytest.mark.asyncio
async def test_consultar_seguimiento_success() -> None:
    captured_payload: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        if request.url.path == "/api/v2/seguimiento.json":
            await request.aread()
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "remito": "2R-55",
                    "estado": "En distribución",
                    "historial": [
                        {"evento": "Ingreso a planta", "fecha": "2026-10-28 10:00:00"},
                        {"evento": "En camino", "fecha": "2026-10-28 14:00:00"},
                    ],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = MarcoPostalClient(
        api_url="https://marcopostal.epresis.com/api/v2",
        token="MOCK_TOKEN",
        transport=transport,
    )

    res = await client.consultar_seguimiento("2R-55")
    assert res["remito"] == "2R-55"
    assert res["estado"] == "En distribución"
    assert len(res["historial"]) == 2
    assert captured_payload["remito"] == "2R-55"
    assert captured_payload["api_token"] == "MOCK_TOKEN"
