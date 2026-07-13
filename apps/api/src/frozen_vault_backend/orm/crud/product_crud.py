"""CRUD operations for the product model."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from frozen_vault_backend.config import config
from frozen_vault_backend.exceptions import InvalidProductLocationError, InvalidProductTypeError
from frozen_vault_backend.orm.crud.base_crud import CRUDBase
from frozen_vault_backend.orm.enums.base_enums import OrderByEnum
from frozen_vault_backend.orm.models.db_models import Product, ProductLocation, ProductType
from frozen_vault_backend.orm.schemas.product_schemas import ProductCreate, ProductUpdate


class CRUDProduct(CRUDBase[Product, ProductCreate, ProductUpdate]):
    """CRUD operations for product model."""

    def _collect_scalar_values(self, obj_dict: dict[str, Any], session: Session) -> dict[str, Any]:
        """Resolve foreign keys and map external names to model column names."""
        result = {}

        # Map product_name to name if present
        if "product_name" in obj_dict:
            result["name"] = obj_dict["product_name"]

        # Copy other scalar fields if present
        for field in ["description", "quantity", "unit", "expiry_date"]:
            if field in obj_dict:
                result[field] = obj_dict[field]

        # Resolve product_type FK if present
        if "product_type" in obj_dict:
            product_type = session.scalar(
                select(ProductType).where(ProductType.name == obj_dict["product_type"])
            )

            if not product_type:
                raise InvalidProductTypeError(obj_dict["product_type"])
            result["product_type_id"] = product_type.id

        # Resolve product_location FK if present
        if "product_location" in obj_dict:
            product_location = session.scalar(
                select(ProductLocation).where(ProductLocation.name == obj_dict["product_location"])
            )
            if not product_location:
                raise InvalidProductLocationError(obj_dict["product_location"])
            result["product_location_id"] = product_location.id

        return result

    def encode_model(self, obj_in: ProductCreate, session: Session) -> Product:
        """Encode a ProductCreate Pydantic model to its SQLAlchemy model counterpart."""
        obj_dict = obj_in.model_dump(exclude_unset=True)
        scalar_values = self._collect_scalar_values(obj_dict, session)
        return Product(
            creation_date=datetime.now(tz=config.brussels_tz),
            image_location="file_path",
            **scalar_values,
        )

    def encode_update_model(self, obj_in: ProductUpdate, session: Session) -> dict[str, Any]:
        """Encode a ProductUpdate Pydantic model to a dictionary of scalar columns."""
        obj_dict = obj_in.model_dump(exclude_unset=True)
        scalar_values = self._collect_scalar_values(obj_dict, session)
        return scalar_values

    def get_names_starting_with(self, product_name: str, session: Session) -> list[str]:
        """Get product names starting with a specific string."""
        scalar_result = session.scalars(
            select(Product.name).where(Product.name.ilike(f"{product_name}%"))
        )
        return list(scalar_result.all())

    def get_multi_filtered_paginated(
        self,
        session: Session,
        *,
        limit: int = 100,
        offset: int = 0,
        name_prefix: str | None = None,
        product_location: str | None = None,
        product_type: str | None = None,
        urgency: str | None = None,
        ascending: bool = False,
        order_by: OrderByEnum = OrderByEnum.ID,
    ) -> Any:
        """Get products filtered by name prefix, location, and type with pagination."""
        order_by_expression = self._get_order_by_expression(order_by, ascending)

        data_statement = select(self.model)
        count_statement = select(func.count()).select_from(self.model)

        if product_type:
            data_statement = data_statement.join(self.model.product_type)
            count_statement = count_statement.join(self.model.product_type)
            data_statement = data_statement.where(ProductType.name == product_type)
            count_statement = count_statement.where(ProductType.name == product_type)

        if product_location:
            data_statement = data_statement.join(self.model.product_location)
            count_statement = count_statement.join(self.model.product_location)
            data_statement = data_statement.where(ProductLocation.name == product_location)
            count_statement = count_statement.where(ProductLocation.name == product_location)

        if name_prefix:
            prefix = name_prefix.strip()
            if prefix:
                data_statement = data_statement.where(self.model.name.ilike(f"{prefix}%"))
                count_statement = count_statement.where(self.model.name.ilike(f"{prefix}%"))

        if urgency in {"soon", "expired"}:
            current_time = datetime.now(tz=config.brussels_tz).replace(tzinfo=None)
            if urgency == "expired":
                data_statement = data_statement.where(self.model.expiry_date < current_time)
                count_statement = count_statement.where(self.model.expiry_date < current_time)
            else:
                threshold = (datetime.now(tz=config.brussels_tz) + timedelta(days=3)).replace(
                    tzinfo=None
                )
                data_statement = data_statement.where(self.model.expiry_date >= current_time)
                data_statement = data_statement.where(self.model.expiry_date <= threshold)
                count_statement = count_statement.where(self.model.expiry_date >= current_time)
                count_statement = count_statement.where(self.model.expiry_date <= threshold)

        data_statement = data_statement.order_by(order_by_expression).offset(offset).limit(limit)

        return self._build_paginated_response(
            session=session,
            data_statement=data_statement,
            count_statement=count_statement,
            offset=offset,
            limit=limit,
        )


product_crud = CRUDProduct(Product)
