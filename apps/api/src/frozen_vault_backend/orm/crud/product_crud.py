"""CRUD operations for the product model."""

from collections import Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from unicodedata import normalize

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from frozen_vault_backend.config import config
from frozen_vault_backend.exceptions import InvalidProductLocationError, InvalidProductTypeError
from frozen_vault_backend.orm.crud.base_crud import CRUDBase, PaginatedResponse
from frozen_vault_backend.orm.enums.base_enums import (
    OrderByEnum,
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.models.db_models import Product, ProductLocation, ProductType
from frozen_vault_backend.orm.schemas.product_schemas import (
    ProductCreate,
    ProductUpdate,
    calculate_best_quality_until,
)


def _normalise_analytics_name(value: str) -> str:
    """Normalise harmless text differences before product-name grouping."""
    return " ".join(normalize("NFKC", value).casefold().split())


def _merge_similar_name_groups(
    groups: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge only mutual, unambiguous name matches at or above 95%."""
    candidates: dict[tuple[str, str], list[tuple[str, str]]] = {key: [] for key in groups}
    keys = list(groups)
    for index, key in enumerate(keys):
        for other_key in keys[index + 1 :]:
            if key[0] != other_key[0]:
                continue
            score = SequenceMatcher(None, key[1], other_key[1], autojunk=False).ratio()
            shorter, longer = sorted((key[1], other_key[1]), key=len)
            is_one_character_prefix = (
                len(shorter) >= 3 and len(longer) == len(shorter) + 1 and longer.startswith(shorter)
            )
            if score >= 0.95 or is_one_character_prefix:
                candidates[key].append(other_key)
                candidates[other_key].append(key)

    star_clusters = {
        key: matches
        for key, matches in candidates.items()
        if len(matches) > 1 and all(candidates[match] == [key] for match in matches)
    }
    star_leaves = {match for matches in star_clusters.values() for match in matches}
    merged: list[dict[str, Any]] = []
    consumed: set[tuple[str, str]] = set()
    for key in keys:
        if key in consumed or key in star_leaves:
            continue
        matches = candidates[key]
        if key in star_clusters:
            group_keys = [key, *star_clusters[key]]
        elif len(matches) == 1 and candidates[matches[0]] == [key]:
            group_keys = [key, matches[0]]
        else:
            group_keys = [key]

        preferred_key, *secondary_keys = sorted(
            group_keys,
            key=lambda candidate: (
                -groups[candidate]["entry_count"],
                -groups[candidate]["weight_g"],
                -groups[candidate]["boxes"],
                -groups[candidate]["bottles"],
                candidate[1],
            ),
        )
        row = {**groups[preferred_key]}
        row["items"] = list(row["items"])
        for secondary_key in secondary_keys:
            secondary = groups[secondary_key]
            for field in ("entry_count", "weight_g", "boxes", "bottles"):
                row[field] += secondary[field]
            row["items"].extend(secondary["items"])

        display_names: Counter[str] = row.pop("display_names")
        row.pop("normalised_name")
        row["name"] = sorted(
            display_names.items(), key=lambda item: (-item[1], item[0].casefold(), item[0])
        )[0][0]
        merged.append(row)
        consumed.update(group_keys)

    return merged


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
        scalar_values.pop("expiry_date", None)
        return scalar_values

    def get_names_starting_with(self, product_name: str, session: Session) -> list[str]:
        """Get product names starting with a specific string."""
        scalar_result = session.scalars(
            select(Product.name)
            .where(Product.name.istartswith(product_name, autoescape=True))
            .group_by(Product.name)
            .order_by(func.lower(Product.name), Product.name)
            .limit(10)
        )
        return list(scalar_result.all())

    def get_freezer_analytics(
        self, session: Session, *, now: datetime | None = None
    ) -> dict[str, dict[str, Any]]:
        """Aggregate unit-safe quantities and expiry counts for all storage locations."""
        current_time = now or datetime.now(tz=config.brussels_tz)
        if current_time.tzinfo is None or current_time.tzinfo.utcoffset(current_time) is None:
            current_time = config.brussels_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(config.brussels_tz)

        location_values = tuple(location.value for location in ProductLocationEnum)
        scope_keys = ("all", *location_values)
        summaries: dict[str, dict[str, Any]] = {
            key: {"entry_count": 0, "weight_g": 0, "boxes": 0, "bottles": 0} for key in scope_keys
        }
        type_totals: dict[str, dict[str, dict[str, Any]]] = {key: {} for key in scope_keys}
        name_totals: dict[str, dict[tuple[str, str], dict[str, Any]]] = {
            key: {} for key in scope_keys
        }
        expiry_totals: dict[str, Counter[Any]] = {key: Counter() for key in scope_keys}

        rows = session.execute(
            select(
                Product.id,
                Product.name,
                Product.quantity,
                Product.unit,
                Product.expiry_date,
                ProductType.name,
                ProductLocation.name,
            )
            .join(Product.product_type)
            .join(Product.product_location)
            .where(ProductLocation.name.in_(location_values))
        ).all()

        for product_id, name, quantity, unit, expiry_date, product_type, location in rows:
            type_value = ProductTypeEnum(product_type).value
            location_value = ProductLocationEnum(location).value
            cleaned_name = " ".join(name.split())
            normalised_name = _normalise_analytics_name(name)
            item = {
                "id": product_id,
                "name": cleaned_name,
                "quantity": quantity,
                "unit": unit,
                "location": location_value,
                "expiry_date": expiry_date,
            }

            for scope_key in ("all", location_value):
                summary = summaries[scope_key]
                summary["entry_count"] += 1
                if unit == ProductUnitEnum.GRAM:
                    summary["weight_g"] += quantity
                elif unit == ProductUnitEnum.BOXES:
                    summary["boxes"] += quantity
                elif unit == ProductUnitEnum.BOTTLES:
                    summary["bottles"] += quantity

                type_summary = type_totals[scope_key].setdefault(
                    type_value,
                    {
                        "type": type_value,
                        "entry_count": 0,
                        "weight_g": 0,
                        "boxes": 0,
                        "bottles": 0,
                        "items": [],
                    },
                )
                type_summary["items"].append(item)
                type_summary["entry_count"] += 1
                if unit == ProductUnitEnum.GRAM:
                    type_summary["weight_g"] += quantity
                elif unit == ProductUnitEnum.BOXES:
                    type_summary["boxes"] += quantity
                elif unit == ProductUnitEnum.BOTTLES:
                    type_summary["bottles"] += quantity

                name_summary = name_totals[scope_key].setdefault(
                    (type_value, normalised_name),
                    {
                        "type": type_value,
                        "normalised_name": normalised_name,
                        "display_names": Counter(),
                        "entry_count": 0,
                        "weight_g": 0,
                        "boxes": 0,
                        "bottles": 0,
                        "items": [],
                    },
                )
                name_summary["items"].append(item)
                name_summary["display_names"][cleaned_name] += 1
                name_summary["entry_count"] += 1
                if unit == ProductUnitEnum.GRAM:
                    name_summary["weight_g"] += quantity
                elif unit == ProductUnitEnum.BOXES:
                    name_summary["boxes"] += quantity
                elif unit == ProductUnitEnum.BOTTLES:
                    name_summary["bottles"] += quantity

                if expiry_date is not None:
                    expiry_totals[scope_key][expiry_date.date()] += 1

        for scope_key, summary in summaries.items():
            type_breakdown = list(type_totals[scope_key].values())
            name_breakdown = _merge_similar_name_groups(name_totals[scope_key])
            max_type_weight = max((row["weight_g"] for row in type_breakdown), default=0)
            max_name_weight = max((row["weight_g"] for row in name_breakdown), default=0)
            for row in type_breakdown:
                row["items"].sort(
                    key=lambda item: (item["expiry_date"], item["name"].casefold(), item["id"])
                )
                row["weight_percentage"] = (
                    round(row["weight_g"] * 100 / max_type_weight, 1) if max_type_weight else 0
                )
            for row in name_breakdown:
                row["items"].sort(
                    key=lambda item: (item["expiry_date"], item["name"].casefold(), item["id"])
                )
                row["weight_percentage"] = (
                    round(row["weight_g"] * 100 / max_name_weight, 1) if max_name_weight else 0
                )
            type_breakdown.sort(
                key=lambda row: (-row["weight_g"], -row["boxes"], -row["bottles"], row["type"])
            )
            name_breakdown.sort(
                key=lambda row: (
                    -row["weight_g"],
                    -row["boxes"],
                    -row["bottles"],
                    row["name"].casefold(),
                )
            )
            max_expiry_count = max(expiry_totals[scope_key].values(), default=0)
            expiry_distribution = [
                {
                    "date": expiry_date.isoformat(),
                    "label": expiry_date.strftime("%d %b"),
                    "year": expiry_date.year,
                    "entry_count": count,
                    "height_percentage": round(count * 100 / max_expiry_count, 1),
                    "is_expired": expiry_date < current_time.date(),
                }
                for expiry_date, count in sorted(expiry_totals[scope_key].items())
            ]
            summary.update(
                {
                    "type_count": len(type_breakdown),
                    "name_count": len(name_breakdown),
                    "type_breakdown": type_breakdown,
                    "name_breakdown": name_breakdown,
                    "expiry_distribution": expiry_distribution,
                    "max_expiry_count": max_expiry_count,
                }
            )

        return summaries

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

        def quality_date(product: Product) -> datetime:
            return calculate_best_quality_until(
                creation_date=product.creation_date, product_type=product.product_type.name
            )

        if urgency in {"soon", "expired"}:
            products = list(
                session.scalars(
                    data_statement.options(*self.recursive_options).order_by(order_by_expression)
                ).all()
            )
            current_time = datetime.now(tz=config.brussels_tz)
            threshold = current_time + timedelta(days=3)

            if urgency == "expired":
                products = [product for product in products if quality_date(product) < current_time]
            else:
                products = [
                    product
                    for product in products
                    if current_time <= quality_date(product) <= threshold
                ]

            if order_by == OrderByEnum.EXPIRY_DATE:
                products.sort(
                    key=lambda product: (quality_date(product), product.id), reverse=not ascending
                )

            return PaginatedResponse(
                data=products[offset : offset + limit],
                total=len(products),
                offset=offset,
                limit=limit,
            )

        if order_by == OrderByEnum.EXPIRY_DATE:
            products = list(session.scalars(data_statement.options(*self.recursive_options)).all())
            products.sort(
                key=lambda product: (quality_date(product), product.id), reverse=not ascending
            )
            return PaginatedResponse(
                data=products[offset : offset + limit],
                total=len(products),
                offset=offset,
                limit=limit,
            )

        data_statement = data_statement.order_by(order_by_expression).offset(offset).limit(limit)

        return self._build_paginated_response(
            session=session,
            data_statement=data_statement,
            count_statement=count_statement,
            offset=offset,
            limit=limit,
        )


product_crud = CRUDProduct(Product)
