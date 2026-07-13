"""CRUD operations for product location model."""

from frozen_vault_backend.orm.crud.base_crud import CRUDBase
from frozen_vault_backend.orm.models.db_models import ProductType
from frozen_vault_backend.orm.schemas.product_type_schemas import (
    ProductTypeCreate,
    ProductTypeUpdate,
)


class CRUDProductType(CRUDBase[ProductType, ProductTypeCreate, ProductTypeUpdate]):
    """CRUD operations for product location model."""


product_type_crud = CRUDProductType(ProductType)
