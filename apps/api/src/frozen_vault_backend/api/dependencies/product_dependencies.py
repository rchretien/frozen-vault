"""Dependencies for product routes."""

from typing import Annotated

from fastapi import Body, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND

from frozen_vault_backend.orm.crud.product_crud import product_crud
from frozen_vault_backend.orm.database import get_session
from frozen_vault_backend.orm.models.db_models import Product
from frozen_vault_backend.orm.schemas.product_schemas import ProductUpdate

SessionDependency = Annotated[Session, Depends(get_session)]


def get_db_product(product_id: int, session: SessionDependency) -> Product:
    """Get a product from the database."""
    product = product_crud.get(session=session, row_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Product not found in the database."
        )
    return product


def get_validated_product_for_update(
    product_id: int, product_update: Annotated[ProductUpdate, Body()], session: SessionDependency
) -> tuple[Product, ProductUpdate]:
    """Get a product and validate the update data against it."""
    product = product_crud.get(session=session, row_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Product not found in the database."
        )

    # Validate update data against existing product
    product_update.validate_against_existing_product(product)

    return product, product_update


ProductDependency = Annotated[Product, Depends(get_db_product)]
ValidatedProductUpdateDependency = Annotated[
    tuple[Product, ProductUpdate], Depends(get_validated_product_for_update)
]
