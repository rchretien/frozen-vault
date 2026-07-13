"""Data models for product type."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from frozen_vault_backend.orm.enums.base_enums import ProductTypeEnum
from frozen_vault_backend.orm.models.db_models import ProductType


class ProductTypeBase(BaseModel):
    """Base class for product type."""

    name: ProductTypeEnum = Field(..., title="Product type name", min_length=1, max_length=50)


class ProductTypeCreate(ProductTypeBase):
    """Create product type."""


class ProductTypeUpdate(ProductTypeBase):
    """Update product type."""


class ProductTypeRead(ProductTypeBase):
    """Read product type model."""

    id: int = Field(..., title="Product type ID", ge=1)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, product_type: ProductType) -> Self:
        """Create a ProductTypeRead instance from a ProductType model instance."""
        return cls(id=product_type.id, name=ProductTypeEnum(product_type.name))


class ProductTypeReadList(BaseModel):
    """Read product type list."""

    product_type_list: list[ProductTypeRead] = Field(
        ..., title="Product types", description="Product type list"
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_db_product_type_list(cls, product_type_list: list[ProductType]) -> Self:
        """Create a ProductTypeReadList instance from a list of ProductTypeRead."""
        return cls(
            product_type_list=[
                ProductTypeRead.from_model(product_type) for product_type in product_type_list
            ]
        )
