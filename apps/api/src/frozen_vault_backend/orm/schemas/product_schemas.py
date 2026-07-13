"""Data models for product."""

import re
from datetime import datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from frozen_vault_backend.config import config
from frozen_vault_backend.exceptions import InvalidExpiryDateError
from frozen_vault_backend.orm.crud.base_crud import PaginatedResponse
from frozen_vault_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.models.db_models import Product


class ProductName(BaseModel):
    """Data model for a product name."""

    name: str = Field(
        ..., title="Product name", min_length=1, max_length=50, description="Product name"
    )

    @field_validator("name")
    @classmethod
    def sentence_case_name(cls, value: str) -> str:
        """Convert the product name to sentence case."""
        return value.capitalize()


class ProductNameList(BaseModel):
    """Data model for a list of product names."""

    names: list[ProductName] = Field(..., title="List of product names")

    @classmethod
    def from_list(cls, product_names: list[str]) -> Self:
        """Create a ProductNameList instance from a list of product names."""
        return cls(names=[ProductName(name=name) for name in product_names])


def _ensure_brussels_timezone(value: datetime) -> datetime:
    """Return a timezone-aware datetime normalised to the Brussels timezone."""
    tz = config.brussels_tz
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return tz.localize(value)
    return value.astimezone(tz)


class ProductBase(BaseModel):
    """Base class for product."""

    product_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        title="Product name",
        description="Product name",
        examples=["Filet de poulet"],
    )
    description: str = Field(
        default="", title="Product description", max_length=256, description="Product description"
    )
    quantity: int = Field(..., title="Product quantity", ge=1, description="Product quantity")
    unit: ProductUnitEnum = Field(
        ..., title="Product unit", min_length=1, max_length=50, description="Product unit"
    )
    expiry_date: datetime = Field(
        ...,
        title="Product expiry date",
        description="Product expiry date",
        examples=[datetime.now(tz=config.brussels_tz) + timedelta(hours=1)],
    )
    product_location: ProductLocationEnum = Field(
        ..., title="Product location", description="Product location"
    )
    product_type: ProductTypeEnum = Field(..., title="Product type", description="Product type")


class ProductCreate(ProductBase):
    """Create product."""

    def validate_against_creation_date(self, creation_date: datetime) -> None:
        """Validate create data against the creation date that will be persisted."""
        expiry_date = _ensure_brussels_timezone(self.expiry_date)
        created_at = _ensure_brussels_timezone(creation_date)

        if expiry_date < created_at:
            raise InvalidExpiryDateError(
                f"Expiry date ({expiry_date.isoformat()}) cannot be earlier than "
                f"creation date ({created_at.isoformat()})"
            )


class ProductUpdate(BaseModel):
    """Update product - all fields optional for partial updates (PATCH semantics)."""

    product_name: str | None = Field(
        None,
        min_length=1,
        max_length=50,
        title="Product name",
        description="Product name",
        examples=["Filet de poulet"],
    )
    description: str | None = Field(
        None, title="Product description", max_length=256, description="Product description"
    )
    quantity: int | None = Field(
        None, title="Product quantity", ge=1, description="Product quantity"
    )
    unit: ProductUnitEnum | None = Field(
        None, title="Product unit", min_length=1, max_length=50, description="Product unit"
    )
    expiry_date: datetime | None = Field(
        None,
        title="Product expiry date",
        description="Product expiry date",
        examples=[datetime.now(tz=config.brussels_tz) + timedelta(hours=1)],
    )
    product_location: ProductLocationEnum | None = Field(
        None, title="Product location", description="Product location"
    )
    product_type: ProductTypeEnum | None = Field(
        None, title="Product type", description="Product type"
    )

    def validate_against_existing_product(self, existing_product: Product) -> None:
        """Validate update data against existing product."""
        if self.expiry_date is not None:
            expiry_date = _ensure_brussels_timezone(self.expiry_date)
            creation_date = _ensure_brussels_timezone(existing_product.creation_date)

            if expiry_date < creation_date:
                raise InvalidExpiryDateError(
                    f"Expiry date ({expiry_date.isoformat()}) cannot be earlier than "
                    f"creation date ({creation_date.isoformat()})"
                )


class ProductRead(ProductBase):
    """Read product model."""

    id: int = Field(..., title="Product ID", ge=1)
    creation_date: datetime = Field(
        ..., title="Product creation date", description="Product creation date"
    )
    image_location: str = Field(
        ...,
        title="Product image location",
        min_length=1,
        max_length=256,
        description="Product image location on the server",
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, model: Product) -> Self:
        """Create a ProductRead instance from a Product model instance."""
        return cls(
            id=model.id,
            product_name=model.name,
            description=model.description,
            quantity=model.quantity,
            unit=ProductUnitEnum(model.unit),
            creation_date=_ensure_brussels_timezone(model.creation_date),
            expiry_date=_ensure_brussels_timezone(model.expiry_date),
            product_location=ProductLocationEnum(model.product_location.name),
            product_type=ProductTypeEnum(model.product_type.name),
            image_location=model.image_location,
        )

    @field_validator("image_location")
    @classmethod
    def validate_image_location(cls, value: str) -> str:
        """Validate if image location is a valid UNIX file path."""

        def is_valid_unix_file_path(file_path: str) -> bool:
            """Check if a string is a valid UNIX file path."""
            pattern = re.compile(r"^(\/)?([^/\0]+(\/)?)+$")
            return bool(pattern.match(file_path))

        if not is_valid_unix_file_path(value):
            raise ValueError("Invalid UNIX file path")  # noqa: EM101, TRY003
        return value


class ProductReadList(BaseModel):
    """List of product models."""

    products: list[ProductRead] = Field(..., title="List of products")
    next_offset: int = Field(
        ..., description="Database index of the last product in the list.", ge=0
    )
    total: int = Field(
        ...,
        description="Total number of products the endpoint can return when called with a given sequence of filters.",
        ge=0,
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_paginated_response(cls, paginated_response: PaginatedResponse[Product]) -> Self:
        """Create a ProductReadList instance from a PaginatedResponse instance."""
        return cls(
            products=[ProductRead.from_model(product) for product in paginated_response.data],
            next_offset=paginated_response.offset
            + min(paginated_response.limit, len(paginated_response.data)),
            total=paginated_response.total,
        )


class CreatedProduct(BaseModel):
    """Data model for a created product."""

    product_id: int = Field(..., description="ID of the created product.")
    message: str = Field(..., description="Message about the created product")

    @classmethod
    def from_model(cls, model: Product) -> Self:
        """Create a CreatedProduct instance from a Product model instance."""
        return cls(product_id=model.id, message="Product created successfully")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message.")
