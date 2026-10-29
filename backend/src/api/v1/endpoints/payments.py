"""Endpoints de Pagos y Checkout.

Re-exporta el router de infraestructura para compatibilidad de importación directa.
"""

from src.infrastructure.api.v1.payments.router import router

__all__ = ["router"]
