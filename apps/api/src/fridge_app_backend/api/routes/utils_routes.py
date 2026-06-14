"""Endpoints for utility functions."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from fridge_app_backend.api.deployment_info import DeploymentInfo, get_deployment_info
from fridge_app_backend.orm.crud.product_location_crud import product_location_crud
from fridge_app_backend.orm.crud.product_type_crud import product_type_crud
from fridge_app_backend.orm.database import get_session
from fridge_app_backend.orm.schemas.product_location_schemas import ProductLocationReadList
from fridge_app_backend.orm.schemas.product_type_schemas import ProductTypeReadList

utils_router = APIRouter(prefix="/utils", tags=["Utilities"])


@utils_router.get("/deployment")
def get_deployment(request: Request) -> DeploymentInfo:
    """Get public deployment and runtime metadata."""
    return get_deployment_info(request)


@utils_router.get("/product_type_list")
async def get_product_type_list(
    *,
    session: Session = Depends(get_session),  # noqa: B008
) -> ProductTypeReadList:
    """Get all product types."""
    return ProductTypeReadList.from_db_product_type_list(
        product_type_list=product_type_crud.get_all(session)
    )


@utils_router.get("/product_location_list")
async def get_product_location_list(
    *,
    session: Session = Depends(get_session),  # noqa: B008
) -> ProductLocationReadList:
    """Get all product locations."""
    return ProductLocationReadList.from_db_product_location_list(
        product_location_list=product_location_crud.get_all(session)
    )
