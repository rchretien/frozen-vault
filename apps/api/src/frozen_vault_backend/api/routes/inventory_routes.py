"""Endpoints for interacting with the fridge inventory."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND

from frozen_vault_backend.api.dependencies.product_dependencies import (
    ProductDependency,
    SessionDependency,
    ValidatedProductUpdateDependency,
)
from frozen_vault_backend.config import config
from frozen_vault_backend.orm.crud.product_crud import product_crud
from frozen_vault_backend.orm.enums.base_enums import OrderByEnum
from frozen_vault_backend.orm.schemas.product_schemas import (
    CreatedProduct,
    ErrorResponse,
    ProductCreate,
    ProductName,
    ProductNameList,
    ProductRead,
    ProductReadList,
)

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])


@inventory_router.post(
    "/create",
    responses={
        HTTP_201_CREATED: {"model": CreatedProduct, "description": "Product successfully created"}
    },
    status_code=HTTP_201_CREATED,
)
async def create_product(
    create_product_in: ProductCreate, session: SessionDependency
) -> CreatedProduct:
    """Create a new product."""
    create_product_in.validate_against_creation_date(datetime.now(tz=config.brussels_tz))
    return CreatedProduct.from_model(product_crud.create(session, obj_in=create_product_in))


@inventory_router.get(
    "/list",
    responses={HTTP_200_OK: {"model": ProductReadList, "description": "List of products"}},
    status_code=HTTP_200_OK,
)
async def get_product_list(
    *,
    ascending: bool = Query(default=False, description="Sort in ascending order"),
    limit: int = Query(default=10, description="Number of products to return"),
    offset: int = Query(default=0, description="Number of records to skip for pagination"),
    order_by: OrderByEnum = Query(default=OrderByEnum.ID, description="Order by a specific column"),  # noqa: B008
    session: SessionDependency,
) -> ProductReadList:
    """Get all products."""
    return ProductReadList.from_paginated_response(
        paginated_response=product_crud.get_multi_paginated(
            session=session, limit=limit, offset=offset, ascending=ascending, order_by=order_by
        )
    )


@inventory_router.get(
    "/startswith",
    status_code=HTTP_200_OK,
    responses={HTTP_200_OK: {"model": ProductNameList, "description": "List of product names"}},
)
async def get_product_names_starting_with(
    session: SessionDependency,
    product_name: Annotated[ProductName, Query(description="Name of the product to search for")],
) -> ProductNameList:
    """Get all products starting with a specific name."""
    return ProductNameList.from_list(
        product_names=product_crud.get_names_starting_with(
            product_name=product_name.name, session=session
        )
    )


@inventory_router.patch(
    "/update",
    responses={
        HTTP_200_OK: {"model": ProductRead, "description": "Product successfully updated"},
        HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Product not found"},
    },
    status_code=HTTP_200_OK,
)
async def update_product(
    product_id: int, validated_data: ValidatedProductUpdateDependency, session: SessionDependency
) -> ProductRead:
    """Update a product."""
    _, product_update = validated_data
    return ProductRead.from_model(
        product_crud.update(session=session, row_id=product_id, obj_in=product_update)
    )


@inventory_router.delete(
    "/delete",
    responses={
        HTTP_204_NO_CONTENT: {"description": "Product successfully deleted"},
        HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Product not found"},
    },
    status_code=HTTP_204_NO_CONTENT,
)
async def delete_product(
    product_id: int, product: ProductDependency, session: SessionDependency
) -> Response:
    """Delete a product."""
    product_crud.remove(session=session, row_id=product.id)
    return Response(status_code=HTTP_204_NO_CONTENT)
