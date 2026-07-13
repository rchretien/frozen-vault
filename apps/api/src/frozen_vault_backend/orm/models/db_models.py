"""SQLAlchemy ORM model definitions for the FrozenVault backend."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from frozen_vault_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)


def enum_values(enum_cls):
    """Persist enum values instead of member names."""
    return [item.value for item in enum_cls]


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class BaseWithID(Base):
    """Base class for all ORM with an ID field."""

    __abstract__ = True

    # ID field used as primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)


class ProductType(BaseWithID):
    """Product type model."""

    __tablename__ = "product_type"

    name: Mapped[ProductTypeEnum] = mapped_column(
        SQLAlchemyEnum(ProductTypeEnum, values_callable=enum_values), unique=True, nullable=False
    )

    # Relationship with the Product model (one-to-many)
    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_type")


class ProductLocation(BaseWithID):
    """Location model."""

    __tablename__ = "product_location"

    name: Mapped[ProductLocationEnum] = mapped_column(
        SQLAlchemyEnum(ProductLocationEnum, values_callable=enum_values), unique=True
    )

    # Relationship with the Product model (one-to-many)
    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_location")


class Product(BaseWithID):
    """Product model."""

    __tablename__ = "product"

    # Define columns
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer, CheckConstraint("quantity >= 1"))
    unit: Mapped[ProductUnitEnum] = mapped_column(
        SQLAlchemyEnum(ProductUnitEnum, values_callable=enum_values),
        default=ProductUnitEnum.GRAM,
        nullable=False,
    )
    creation_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    image_location: Mapped[str] = mapped_column(String, nullable=True)

    # Relationship with the ProductType model (many-to-one)
    product_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_type.id"), nullable=False
    )
    product_type: Mapped[ProductType] = relationship(ProductType, back_populates="products")

    # Relationship with the ProductLocation model (many-to-one)
    product_location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_location.id"), nullable=False
    )
    product_location: Mapped[ProductLocation] = relationship(
        ProductLocation, back_populates="products"
    )

    # Adding check constraints spanning several columns to the table
    __table_args__ = (
        CheckConstraint(sqltext="expiry_date > creation_date", name="expiry_date_check"),
    )


def init_product_type_table(session: Session) -> None:
    """Initialise the product type table from ProductTypeEnum."""
    session.add_all([ProductType(name=product_type) for product_type in ProductTypeEnum])


def init_product_location_table(session: Session) -> None:
    """Initialise the location table from ProductLocationEnum."""
    session.add_all([ProductLocation(name=location) for location in ProductLocationEnum])
