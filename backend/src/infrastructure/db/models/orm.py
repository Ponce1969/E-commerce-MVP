from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.session import Base


class AdminUserORM(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CommercialListORM(Base):
    __tablename__ = "commercial_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    prices: Mapped[list["ProductPriceORM"]] = relationship(
        "ProductPriceORM", back_populates="commercial_list", cascade="all, delete-orphan"
    )
    customers: Mapped[list["CustomerORM"]] = relationship(
        "CustomerORM", back_populates="commercial_list"
    )


class ProductORM(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    presentation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, default="General", index=True
    )
    iva_rate: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("0.22")
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    tech_sheet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_stock_alert: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    allow_backorder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    prices: Mapped[list["ProductPriceORM"]] = relationship(
        "ProductPriceORM", back_populates="product", cascade="all, delete-orphan"
    )


class ProductPriceORM(Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "commercial_list_id", name="uq_product_commercial_list"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commercial_list_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("commercial_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cost_iva_inc: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    markup_percentage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    price_iva_inc: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflict_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["ProductORM"] = relationship("ProductORM", back_populates="prices")
    commercial_list: Mapped["CommercialListORM"] = relationship(
        "CommercialListORM", back_populates="prices"
    )


class CustomerORM(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_type: Mapped[str] = mapped_column(String(10), nullable=False)
    document_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_whatsapp: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_list_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commercial_lists.id"), nullable=False
    )
    reception_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    authorized_persons: Mapped[str | None] = mapped_column(Text, nullable=True)
    crm_status: Mapped[str] = mapped_column(String(20), default="ACTIVO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    commercial_list: Mapped["CommercialListORM"] = relationship(
        "CommercialListORM", back_populates="customers"
    )
    orders: Mapped[list["OrderORM"]] = relationship("OrderORM", back_populates="customer")


class OrderORM(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True
    )
    order_status: Mapped[str] = mapped_column(
        String(30), default="PENDIENTE", nullable=False, index=True
    )
    delivery_type: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    customer: Mapped["CustomerORM"] = relationship("CustomerORM", back_populates="orders")
    items: Mapped[list["OrderItemORM"]] = relationship(
        "OrderItemORM", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0000"), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["OrderORM"] = relationship("OrderORM", back_populates="items")
    product: Mapped["ProductORM"] = relationship("ProductORM")
