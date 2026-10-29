import logging
from collections.abc import Sequence
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class MercadoPagoClient:
    """Cliente asíncrono para Mercado Pago Uruguay (Checkout Pro & Payments API)."""

    def __init__(
        self,
        access_token: str | None = None,
        base_url: str = "https://api.mercadopago.com",
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.access_token = access_token or settings.MP_ACCESS_TOKEN
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def crear_preferencia(
        self,
        order: Any,
        items: Sequence[Any],
    ) -> str:
        """Crea una preferencia de pago en Mercado Pago Checkout Pro.

        Args:
            order: Entidad u objeto ORM de la orden (debe contener id y opcionalmente delivery_cost).
            items: Lista de ítems de la orden (con product/product_id, quantity, unit_price).

        Returns:
            URL del init_point para redirigir al usuario al checkout de Mercado Pago.
        """
        endpoint = f"{self.base_url}/checkout/preferences"

        items_payload: list[dict[str, Any]] = []
        for it in items:
            title = "Producto"
            if hasattr(it, "product") and it.product and hasattr(it.product, "name"):
                title = it.product.name
            elif hasattr(it, "product_name") and it.product_name:
                title = str(it.product_name)
            elif hasattr(it, "product_id"):
                title = f"Producto #{it.product_id}"

            unit_price = float(it.unit_price) if hasattr(it, "unit_price") else 0.0
            quantity = int(it.quantity) if hasattr(it, "quantity") else 1

            items_payload.append(
                {
                    "id": str(getattr(it, "product_id", getattr(it, "id", ""))),
                    "title": title,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "currency_id": "UYU",
                }
            )

        # Si hay costo de envío mayor a cero, se agrega como ítem de flete/envío
        delivery_cost = float(getattr(order, "delivery_cost", 0) or 0)
        if delivery_cost > 0:
            items_payload.append(
                {
                    "id": "shipping_fee",
                    "title": "Costo de Envío",
                    "quantity": 1,
                    "unit_price": delivery_cost,
                    "currency_id": "UYU",
                }
            )

        payload: dict[str, Any] = {
            "items": items_payload,
            "external_reference": str(order.id),
            "back_urls": {
                "success": settings.MP_BACK_URL_SUCCESS,
                "pending": settings.MP_BACK_URL_PENDING,
                "failure": settings.MP_BACK_URL_FAILURE,
            },
            "auto_return": "approved",
            "statement_descriptor": "DOS RODRIGUEZ",
        }

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(endpoint, json=payload, headers=self._headers)
            if response.status_code >= 400:
                logger.error(
                    "Error creando preferencia Mercado Pago: HTTP %s - %s",
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            data: dict[str, Any] = response.json()
            preference_id = data.get("id")
            if hasattr(order, "preference_id") and preference_id:
                order.preference_id = preference_id

            init_point: str = data.get("init_point") or data.get("sandbox_init_point") or ""
            return init_point

    async def obtener_pago(self, payment_id: str | int) -> dict[str, Any]:
        """Consulta el estado del pago contra la API de pagos de Mercado Pago."""
        endpoint = f"{self.base_url}/v1/payments/{payment_id}"

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.get(endpoint, headers=self._headers)
            if response.status_code >= 400:
                logger.error(
                    "Error consultando pago Mercado Pago %s: HTTP %s - %s",
                    payment_id,
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            data: dict[str, Any] = response.json()
            return data
