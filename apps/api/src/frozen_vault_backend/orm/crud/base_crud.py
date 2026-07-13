"""Base class for CRUD operations."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import func

from frozen_vault_backend.exceptions import ModelNotHavingAttributeError
from frozen_vault_backend.orm.enums.base_enums import OrderByEnum
from frozen_vault_backend.orm.models.db_models import BaseWithID

ModelType = TypeVar("ModelType", bound=BaseWithID)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


@dataclass
class PaginatedResponse(Generic[ModelType]):
    """Paginated response schema."""

    data: list[ModelType]
    total: int
    offset: int
    limit: int


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations.

    ModelType: SQLAlchemy model,
    CreateSchemaType: Pydantic schema for creating a new model instance,
    UpdateSchemaType: Pydantic schema for updating an existing model instance.
    """

    # Options to control how relationships are loaded when querying the database with the
    # recursive option. Can be overwritten in subclasses if needed.
    recursive_options = (selectinload("*"),)

    def __init__(self, model: type[ModelType]):
        """CRUD object with default methods to Create, Read, Update, Delete (CRUD)."""
        self.model = model

    def encode_model(self, obj_in: CreateSchemaType, session: Session) -> ModelType:
        """Encode a Pydantic model to a SQLAlchemy model."""
        return self.model(**jsonable_encoder(obj_in))

    def encode_update_model(self, obj_in: UpdateSchemaType, session: Session) -> dict[str, Any]:
        """Encode a Pydantic model to a dictionary of scalar values for updates."""
        return obj_in.model_dump(exclude_unset=True)

    def get(self, session: Session, row_id: int) -> ModelType | None:
        """Get a single model instance by ID."""
        result: ModelType | None = session.get(self.model, row_id)
        return result

    def _get_order_by_expression(
        self, order_by: OrderByEnum, ascending: bool = False
    ) -> ColumnElement[bool]:
        """Get the order by expression."""
        if not hasattr(self.model, order_by.value):
            raise ModelNotHavingAttributeError(
                model_name=self.model.__name__, attribute=order_by.value
            )
        return (  # type: ignore[no-any-return]
            getattr(self.model, order_by.value).asc()
            if ascending
            else getattr(self.model, order_by.value).desc()
        )

    def get_multi_paginated(
        self,
        session: Session,
        offset: int = 0,
        limit: int = 100,
        *,
        ascending: bool = False,
        order_by: OrderByEnum = OrderByEnum.ID,
    ) -> PaginatedResponse[ModelType]:
        """Get multiple model instances with pagination."""
        # Get the order by expression (raises ModelNotHavingAttributeError if invalid)
        order_by_expression = self._get_order_by_expression(order_by, ascending)

        # Build the data query with ordering, offset, and limit
        data_statement = (
            select(self.model).order_by(order_by_expression).offset(offset).limit(limit)
        )

        # Count total records directly from the base model (more efficient)
        count_statement = select(func.count()).select_from(self.model)

        return self._build_paginated_response(
            session=session,
            data_statement=data_statement,
            count_statement=count_statement,
            offset=offset,
            limit=limit,
        )

    def _build_paginated_response(
        self,
        *,
        session: Session,
        data_statement: Any,
        count_statement: Any,
        offset: int,
        limit: int,
    ) -> PaginatedResponse[ModelType]:
        """Build a paginated response from prepared data and count statements."""
        return PaginatedResponse(
            data=list(session.scalars(data_statement).all()),
            total=session.scalar(count_statement) or 0,
            offset=offset,
            limit=limit,
        )

    def get_all(self, session: Session) -> list[ModelType]:
        """Get all model instances."""
        return list(session.scalars(select(self.model)).all())

    def create(self, session: Session, obj_in: CreateSchemaType) -> ModelType:
        """Create a new database record."""
        db_obj = self.encode_model(obj_in, session)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def create_multi(self, session: Session, obj_in: list[CreateSchemaType]) -> list[ModelType]:
        """Create multiple database records."""
        db_objs = [self.encode_model(obj, session) for obj in obj_in]
        session.add_all(db_objs)
        session.commit()
        for db_obj in db_objs:
            session.refresh(db_obj)
        return db_objs

    def update(self, session: Session, row_id: int, obj_in: UpdateSchemaType) -> ModelType:
        """Update an existing database record."""
        db_obj = session.get(self.model, row_id)

        # Check if the object exists
        if db_obj is None:
            raise NoResultFound

        # Check if all fields are present in the object
        update_data = self.encode_update_model(obj_in, session)
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        # Update the object
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)

        return db_obj

    def remove(self, session: Session, row_id: int) -> ModelType:
        """Delete a database record."""
        db_obj = session.get(self.model, row_id)

        # Check if the object exists
        if db_obj is None:
            raise NoResultFound

        session.delete(db_obj)
        session.commit()
        return db_obj
