from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.models import DeliveryType, PaymentStatus
from src.infrastructure.db.models import OrderORM
from src.main import app


@pytest.mark.asyncio
async def test_webhook_ignored_when_no_payment_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/payments/webhook", json={"type": "ping"})
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        assert "no payment id found" in res.json()["message"]


@pytest.mark.asyncio
async def test_webhook_approves_payment_and_creates_guide() -> None:
    mock_order = MagicMock(spec=OrderORM)
    mock_order.id = 101
    mock_order.payment_status = "PENDING"
    mock_order.order_status = "PENDIENTE"
    mock_order.delivery_type = DeliveryType.CADETERIA_MARCO_POSTAL.value
    mock_order.shipping_street = "Av. Agraciada"
    mock_order.customer = MagicMock()
    mock_order.items = []
    mock_order.remito_postal = None
    mock_order.tracking_url = None

    mock_db_res = MagicMock()
    mock_db_res.scalar_one_or_none.return_value = mock_order

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_db_res
    mock_session.commit.return_value = None

    with (
        patch(
            "src.infrastructure.api.v1.payments.router.get_db_session", return_value=mock_session
        ),
        patch(
            "src.infrastructure.payments.mercadopago_client.MercadoPagoClient.obtener_pago",
            new_callable=AsyncMock,
        ) as mock_get_payment,
        patch(
            "src.infrastructure.logistics.marco_postal_client.MarcoPostalClient.crear_guia",
            new_callable=AsyncMock,
        ) as mock_crear_guia,
    ):
        mock_get_payment.return_value = {
            "status": "approved",
            "external_reference": "101",
        }
        mock_crear_guia.return_value = {
            "status": "success",
            "remito": "2R-101",
            "tracking_url": "https://marcopostal.epresis.com/seguimiento/2R-101",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/payments/webhook",
                json={"action": "payment.updated", "data": {"id": "999888"}},
            )

            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["order_id"] == 101
            assert mock_order.payment_status == PaymentStatus.PAID.value
            assert mock_order.payment_id == "999888"
            mock_crear_guia.assert_called_once_with(order=mock_order, customer=mock_order.customer)
            mock_session.commit.assert_called_once()
