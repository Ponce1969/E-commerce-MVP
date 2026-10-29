import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class MarcoPostalClient:
    """Cliente asíncrono para la API v2 de Marco Postal (ePresis)."""

    def __init__(
        self,
        api_url: str | None = None,
        token: str | None = None,
        sucursal: str | None = None,
        servicio: str | None = None,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = (api_url or settings.MARCO_POSTAL_API_URL).rstrip("/")
        self.token = token or settings.MARCO_POSTAL_TOKEN
        self.sucursal = sucursal or settings.MARCO_POSTAL_SUCURSAL
        self.servicio = servicio or settings.MARCO_POSTAL_SERVICIO
        self.timeout = timeout
        self.transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def crear_guia(self, order: Any, customer: Any | None = None) -> dict[str, Any]:
        """Crea una guía de despacho en ePresis / Marco Postal contra /guias.json.

        Args:
            order: Objeto de la orden con id, shipping_*, delivery_notes, items.
            customer: Objeto opcional del cliente para complementar datos de contacto/facturación.

        Returns:
            dict con la respuesta devuelta por la API de Marco Postal.
        """
        endpoint = f"{self.api_url}/guias.json"
        remito = f"2R-{order.id}"

        # Remitente fijo (Dos Rodríguez)
        remitente_payload = {
            "nombre": settings.SENDER_REMITENTE,
            "empresa": settings.SENDER_EMPRESA,
            "rut": settings.SENDER_RUT,
            "calle": settings.SENDER_CALLE,
            "altura": settings.SENDER_ALTURA,
            "localidad": settings.SENDER_LOCALIDAD,
            "provincia": settings.SENDER_PROVINCIA,
            "cp": settings.SENDER_CP,
            "celular": settings.SENDER_CELULAR,
            "email": settings.SENDER_EMAIL,
        }

        # Comprador / Destinatario mapeado 1:1 y determinista
        recipient_name = getattr(order, "shipping_recipient_name", None) or (
            getattr(customer, "contact_name", None)
            or getattr(customer, "business_name", None)
            or "Cliente 2R"
        )
        doc_num = getattr(order, "shipping_document_number", None) or getattr(
            customer, "document_number", ""
        )
        phone = getattr(order, "shipping_phone", None) or getattr(customer, "phone_whatsapp", "")
        email = getattr(customer, "email", "") if customer else ""

        comprador_payload = {
            "destinatario": recipient_name,
            "documento": doc_num,
            "calle": getattr(order, "shipping_street", "") or "",
            "altura": getattr(order, "shipping_street_number", "") or "",
            "piso": getattr(order, "shipping_apartment", "") or "",
            "localidad": getattr(order, "shipping_city", "") or "",
            "provincia": getattr(order, "shipping_state", "") or "",
            "cp": getattr(order, "shipping_postal_code", "") or "",
            "celular": phone,
            "email": email,
            "observaciones": (
                getattr(order, "shipping_notes", None) or getattr(order, "delivery_notes", "") or ""
            ),
        }

        # Productos y bultos
        items = getattr(order, "items", []) or []
        productos_payload = []
        for it in items:
            desc = "Producto"
            if hasattr(it, "product") and it.product and hasattr(it.product, "name"):
                desc = it.product.name
            elif hasattr(it, "product_name") and it.product_name:
                desc = str(it.product_name)
            elif hasattr(it, "product_id"):
                desc = f"Producto #{it.product_id}"

            productos_payload.append(
                {
                    "descripcion": desc,
                    "cantidad": int(getattr(it, "quantity", 1)),
                }
            )

        payload: dict[str, Any] = {
            "api_token": self.token,
            "sucursal": self.sucursal,
            "servicio": self.servicio,
            "remito": remito,
            "remitente": remitente_payload,
            "comprador": comprador_payload,
            "productos": productos_payload,
            "bultos": len(productos_payload) if productos_payload else 1,
        }

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(endpoint, json=payload, headers=self._headers)
            if response.status_code >= 400:
                logger.error(
                    "Error creando guía Marco Postal para orden %s: HTTP %s - %s",
                    order.id,
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            data: dict[str, Any] = response.json()

            # Guardar remito y constancia/seguimiento en la orden
            tracking_url = (
                data.get("tracking_url")
                or data.get("url_seguimiento")
                or data.get("constancia")
                or f"{self.api_url.replace('/api/v2', '')}/seguimiento/{remito}"
            )
            order.remito_postal = data.get("remito") or remito
            order.tracking_url = tracking_url

            return data

    async def consultar_seguimiento(self, remito: str) -> dict[str, Any]:
        """Consulta el estado del seguimiento contra /seguimiento.json."""
        endpoint = f"{self.api_url}/seguimiento.json"
        payload = {
            "api_token": self.token,
            "remito": remito,
        }

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(endpoint, json=payload, headers=self._headers)
            if response.status_code >= 400:
                logger.error(
                    "Error consultando seguimiento remito %s: HTTP %s - %s",
                    remito,
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            data: dict[str, Any] = response.json()
            return data
