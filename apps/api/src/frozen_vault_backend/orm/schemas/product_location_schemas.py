"""Data models for product location."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from frozen_vault_backend.orm.enums.base_enums import ProductLocationEnum
from frozen_vault_backend.orm.models.db_models import ProductLocation


class ProductLocationBase(BaseModel):
    """Base class for product location."""

    name: ProductLocationEnum = Field(
        ..., title="Product location name", min_length=1, max_length=50
    )


class ProductLocationCreate(ProductLocationBase):
    """Create product location."""


class ProductLocationUpdate(ProductLocationBase):
    """Update product location."""


class ProductLocationRead(ProductLocationBase):
    """Read product location model."""

    id: int = Field(..., title="Product location ID", ge=1)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, product_location: ProductLocation) -> Self:
        """Create a ProductLocationRead instance from a ProductLocation model instance."""
        return cls(id=product_location.id, name=ProductLocationEnum(product_location.name))


class ProductLocationReadList(BaseModel):
    """Read product location list."""

    product_location_list: list[ProductLocationRead] = Field(
        ..., title="Product locations", description="Product location list"
    )

    @classmethod
    def from_db_product_location_list(cls, product_location_list: list[ProductLocation]) -> Self:
        """Create a ProductLocationReadList instance from a list of ProductLocationRead."""
        return cls(
            product_location_list=[
                ProductLocationRead.from_model(product_location)
                for product_location in product_location_list
            ]
        )
