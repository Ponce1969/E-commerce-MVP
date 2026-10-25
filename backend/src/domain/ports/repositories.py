from abc import ABC, abstractmethod

from src.domain.models import CommercialList, Customer, Order, Product


class ProductRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, product_id: int) -> Product | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(
        self,
        category: str | None = None,
        is_published: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Product]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, product: Product) -> Product:
        raise NotImplementedError


class CommercialListRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, list_id: int) -> CommercialList | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str) -> CommercialList | None:
        raise NotImplementedError

    @abstractmethod
    async def list_active(self) -> list[CommercialList]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, commercial_list: CommercialList) -> CommercialList:
        raise NotImplementedError


class CustomerRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, customer_id: int) -> Customer | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> Customer | None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, customer: Customer) -> Customer:
        raise NotImplementedError


class OrderRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, order_id: int) -> Order | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_customer_id(self, customer_id: int) -> list[Order]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, order: Order) -> Order:
        raise NotImplementedError
