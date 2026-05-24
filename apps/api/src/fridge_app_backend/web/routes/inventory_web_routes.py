"""Server-rendered inventory routes for the mobile web UI."""

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from fridge_app_backend.api.dependencies.product_dependencies import SessionDependency
from fridge_app_backend.config import config
from fridge_app_backend.exceptions import (
    InvalidExpiryDateError,
    InvalidProductLocationError,
    InvalidProductTypeError,
)
from fridge_app_backend.orm.crud.product_crud import product_crud
from fridge_app_backend.orm.enums.base_enums import (
    OrderByEnum,
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from fridge_app_backend.orm.schemas.product_schemas import ProductCreate, ProductRead, ProductUpdate
from fridge_app_backend.web.templating import expiry_status, format_date_input, templates

inventory_web_router = APIRouter(include_in_schema=False)

DEFAULT_LIMIT = 10
LIMIT_STEP = 10
FORM_ERROR_FLASH = "Product could not be saved. Check the highlighted fields and try again."
SORT_OPTIONS = {
    "newest": (OrderByEnum.ID, False),
    "expiry": (OrderByEnum.EXPIRY_DATE, True),
    "name_asc": (OrderByEnum.NAME, True),
    "name_desc": (OrderByEnum.NAME, False),
}


def _normalise_filters(
    *,
    q: str = "",
    product_type: str = "",
    product_location: str = "",
    urgency: str = "all",
    sort: str = "newest",
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Normalise UI filter values so templates can rely on stable state."""
    safe_sort = sort if sort in SORT_OPTIONS else "newest"
    safe_limit = max(LIMIT_STEP, limit)
    safe_urgency = urgency if urgency in {"all", "soon", "expired"} else "all"
    return {
        "q": q.strip(),
        "product_type": product_type.strip(),
        "product_location": product_location.strip(),
        "urgency": safe_urgency,
        "sort": safe_sort,
        "limit": safe_limit,
    }


def _list_query_params(filters: dict[str, Any], *, limit: int | None = None) -> dict[str, Any]:
    """Build query parameters for list refreshes and load-more actions."""
    return {
        "q": filters["q"],
        "product_type": filters["product_type"],
        "product_location": filters["product_location"],
        "urgency": filters["urgency"],
        "sort": filters["sort"],
        "limit": limit if limit is not None else filters["limit"],
    }


def _current_path_with_query(request: Request) -> str:
    """Return the current relative path plus query string for return navigation."""
    query_items = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key not in {"flash", "flash_level"}
    ]
    if query_items:
        return f"{request.url.path}?{urlencode(query_items)}"
    return request.url.path


def _safe_return_to(return_to: str | None, *, fallback: str = "/") -> str:
    """Keep return navigation inside the app to avoid open redirects."""
    if return_to and return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return fallback


def _with_query_params(base_url: str, **params: str) -> str:
    """Append query parameters to a relative URL."""
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def _redirect_with_flash(
    *, return_to: str | None, message: str, level: str = "success"
) -> RedirectResponse:
    """Redirect to a safe relative URL with flash feedback attached."""
    safe_return_to = _safe_return_to(return_to)
    return RedirectResponse(
        url=_with_query_params(safe_return_to, flash=message, flash_level=level),
        status_code=HTTP_303_SEE_OTHER,
    )


def _get_inventory_context(
    *,
    request: Request,
    session: SessionDependency,
    q: str,
    product_type: str,
    product_location: str,
    urgency: str,
    sort: str,
    limit: int,
    active_nav: str,
) -> dict[str, Any]:
    """Build the inventory page context shared by full-page and partial renders."""
    filters = _normalise_filters(
        q=q,
        product_type=product_type,
        product_location=product_location,
        urgency=urgency,
        sort=sort,
        limit=limit,
    )
    order_by, ascending = SORT_OPTIONS[filters["sort"]]
    paginated_response = product_crud.get_multi_filtered_paginated(
        session=session,
        limit=filters["limit"],
        offset=0,
        name_prefix=filters["q"] or None,
        product_type=filters["product_type"] or None,
        product_location=filters["product_location"] or None,
        urgency=None if filters["urgency"] == "all" else filters["urgency"],
        order_by=order_by,
        ascending=ascending,
    )
    products = [ProductRead.from_model(product) for product in paginated_response.data]
    grouped_products = {
        "expired": [
            product for product in products if expiry_status(product.expiry_date) == "expired"
        ],
        "expiring-soon": [
            product for product in products if expiry_status(product.expiry_date) == "expiring-soon"
        ],
        "fresh": [product for product in products if expiry_status(product.expiry_date) == "fresh"],
    }
    if filters["urgency"] == "expired":
        group_config = [("expired", "Expired now", "Products that need to be removed or replaced.")]
    elif filters["urgency"] == "soon":
        group_config = [
            ("expired", "Already expired", "Past the safe window and worth checking first."),
            (
                "expiring-soon",
                "Use soon",
                "Still safe, but should be prioritised in the next few days.",
            ),
        ]
    else:
        group_config = [
            ("expired", "Expired now", "Handle these first so they do not get lost in the list."),
            (
                "expiring-soon",
                "Use soon",
                "Build the next meals around these before they cross the line.",
            ),
            ("fresh", "Fresh later", "Everything else that can stay in storage a bit longer."),
        ]
    product_groups = [
        {
            "key": key,
            "title": title,
            "description": description,
            "products": grouped_products[key],
            "count": len(grouped_products[key]),
        }
        for key, title, description in group_config
        if grouped_products[key]
    ]
    has_more = paginated_response.total > filters["limit"]
    soon_count = product_crud.get_multi_filtered_paginated(
        session=session,
        limit=1,
        offset=0,
        urgency="soon",
        order_by=OrderByEnum.EXPIRY_DATE,
        ascending=True,
    ).total
    expired_count = product_crud.get_multi_filtered_paginated(
        session=session,
        limit=1,
        offset=0,
        urgency="expired",
        order_by=OrderByEnum.EXPIRY_DATE,
        ascending=True,
    ).total
    load_more_url = None
    if has_more:
        load_more_url = str(
            request.url_for("render_inventory_list_fragment").include_query_params(
                **_list_query_params(filters, limit=filters["limit"] + LIMIT_STEP)
            )
        )

    current_url = _current_path_with_query(request)
    filter_params = _list_query_params(filters)
    all_params = {**filter_params, "urgency": "all"}
    soon_params = {**filter_params, "urgency": "soon"}
    expired_params = {**filter_params, "urgency": "expired"}
    all_url = str(request.url_for("inventory_home").include_query_params(**all_params))
    soon_url = str(request.url_for("inventory_soon").include_query_params(**soon_params))
    expired_url = str(request.url_for("inventory_soon").include_query_params(**expired_params))

    return {
        "request": request,
        "active_nav": active_nav,
        "products": products,
        "product_groups": product_groups,
        "filters": filters,
        "total": paginated_response.total,
        "soon_count": soon_count,
        "expired_count": expired_count,
        "has_more": has_more,
        "load_more_url": load_more_url,
        "current_url": current_url,
        "filter_urls": {"all": all_url, "soon": soon_url, "expired": expired_url},
        "filter_action_url": str(
            request.url_for("inventory_soon" if active_nav == "soon" else "inventory_home")
        ),
        "sort_options": [
            ("newest", "Newest first"),
            ("expiry", "Expiry soonest"),
            ("name_asc", "Name A-Z"),
            ("name_desc", "Name Z-A"),
        ],
        "product_type_options": [enum.value for enum in ProductTypeEnum],
        "product_location_options": [enum.value for enum in ProductLocationEnum],
        "screen_title": "Expiring soon" if active_nav == "soon" else "Inventory",
        "screen_subtitle": (
            "Use this view to clear items before they go bad."
            if active_nav == "soon"
            else "Track what you have, what is running low, and what needs attention."
        ),
        "flash": request.query_params.get("flash"),
        "flash_level": request.query_params.get("flash_level", "success"),
    }


def _empty_form_data() -> dict[str, str]:
    """Return an empty form data dictionary for create views."""
    return {
        "product_name": "",
        "description": "",
        "quantity": "1",
        "unit": ProductUnitEnum.GRAM.value,
        "expiry_date": "",
        "expiry_date_date": "",
        "product_location": ProductLocationEnum.REFRIGERATOR.value,
        "product_type": ProductTypeEnum.FRUIT.value,
    }


def _form_data_from_product(product: ProductRead) -> dict[str, str]:
    """Build form defaults from an existing product."""
    return {
        "product_name": product.product_name,
        "description": product.description,
        "quantity": str(product.quantity),
        "unit": product.unit.value,
        "expiry_date": format_date_input(product.expiry_date),
        "expiry_date_date": format_date_input(product.expiry_date),
        "product_location": product.product_location.value,
        "product_type": product.product_type.value,
    }


def _render_form_page(
    *,
    request: Request,
    title: str,
    submit_label: str,
    action_url: str,
    form_data: dict[str, str],
    errors: dict[str, str] | None = None,
    active_nav: str = "add",
    return_to: str | None = None,
) -> HTMLResponse:
    """Render the shared product form page."""
    form_errors = errors or {}
    return templates.TemplateResponse(
        request=request,
        name="inventory/form_page.html",
        context={
            "title": title,
            "submit_label": submit_label,
            "action_url": action_url,
            "form_data": form_data,
            "errors": form_errors,
            "active_nav": active_nav,
            "return_to": _safe_return_to(return_to, fallback="/web/inventory"),
            "flash": FORM_ERROR_FLASH if form_errors else None,
            "flash_level": "error",
            "unit_options": [enum.value for enum in ProductUnitEnum],
            "product_type_options": [enum.value for enum in ProductTypeEnum],
            "product_location_options": [enum.value for enum in ProductLocationEnum],
        },
    )


def _render_more_page(request: Request) -> HTMLResponse:
    """Render the lightweight utility page shown from the bottom navigation."""
    return templates.TemplateResponse(
        request=request,
        name="more/index.html",
        context={
            "active_nav": "more",
            "screen_title": "More",
            "screen_subtitle": "Tools, documentation, and the next capabilities planned for this app.",
        },
    )


def _get_home_context(*, request: Request, session: SessionDependency) -> dict[str, Any]:
    """Build the dedicated welcome dashboard context."""
    context = _get_inventory_context(
        request=request,
        session=session,
        q="",
        product_type="",
        product_location="",
        urgency="all",
        sort="newest",
        limit=5,
        active_nav="home",
    )
    expired_preview_response = product_crud.get_multi_filtered_paginated(
        session=session,
        limit=4,
        offset=0,
        urgency="expired",
        order_by=OrderByEnum.EXPIRY_DATE,
        ascending=True,
    )
    expired_preview = [ProductRead.from_model(product) for product in expired_preview_response.data]
    soon_preview_response = product_crud.get_multi_filtered_paginated(
        session=session,
        limit=max(4 - len(expired_preview), 0),
        offset=0,
        urgency="soon",
        order_by=OrderByEnum.EXPIRY_DATE,
        ascending=True,
    )
    urgent_preview = expired_preview + [
        ProductRead.from_model(product) for product in soon_preview_response.data
    ]
    context.update(
        {
            "screen_title": "Welcome",
            "screen_subtitle": "See what needs attention, then jump straight into the right task.",
            "fresh_count": max(
                context["total"] - context["soon_count"] - context["expired_count"], 0
            ),
            "urgent_preview": urgent_preview[:4],
            "recent_preview": context["products"][:5],
        }
    )
    return context


def _validation_errors(exc: ValidationError) -> dict[str, str]:
    """Convert Pydantic validation errors into a field-indexed dictionary."""
    errors = {}
    for error in exc.errors():
        location = error.get("loc", [])
        field_name = str(location[-1]) if location else "__all__"
        errors[field_name] = error.get("msg", "Invalid value")
    return errors


def _product_from_form(
    *,
    product_name: str,
    description: str,
    quantity: str,
    unit: str,
    expiry_date: str,
    product_location: str,
    product_type: str,
) -> dict[str, str]:
    """Return a product payload dictionary from form submissions."""
    return {
        "product_name": product_name,
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "expiry_date": expiry_date,
        "product_location": product_location,
        "product_type": product_type,
    }


def _coalesce_expiry_date(*, expiry_date: str, expiry_date_date: str) -> str:
    """Build a datetime value from a date-only web form input."""
    if expiry_date.strip():
        return expiry_date
    if not expiry_date_date.strip():
        return ""
    return f"{expiry_date_date.strip()}T23:59:59"


def _missing_field_errors(form_data: dict[str, str]) -> dict[str, str]:
    """Return inline errors for empty required fields in HTML form submissions."""
    required_fields = {
        "product_name",
        "quantity",
        "unit",
        "expiry_date",
        "product_location",
        "product_type",
    }
    return {
        field_name: "Field required"
        for field_name, value in form_data.items()
        if field_name in required_fields and not str(value).strip()
    }


@inventory_web_router.get("/", response_class=HTMLResponse, name="home_page")
async def home_page(request: Request, session: SessionDependency) -> HTMLResponse:
    """Render the welcome dashboard page."""
    context = _get_home_context(request=request, session=session)
    return templates.TemplateResponse(request=request, name="home/index.html", context=context)


@inventory_web_router.get("/web/inventory", response_class=HTMLResponse, name="inventory_home")
async def inventory_home(
    request: Request,
    session: SessionDependency,
    q: str = Query(default=""),
    product_type: str = Query(default=""),
    product_location: str = Query(default=""),
    urgency: str = Query(default="all"),
    sort: str = Query(default="newest"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=LIMIT_STEP),
) -> HTMLResponse:
    """Render the dedicated inventory management page."""
    context = _get_inventory_context(
        request=request,
        session=session,
        q=q,
        product_type=product_type,
        product_location=product_location,
        urgency=urgency,
        sort=sort,
        limit=limit,
        active_nav="inventory",
    )
    return templates.TemplateResponse(request=request, name="inventory/index.html", context=context)


@inventory_web_router.get("/web/inventory/soon", response_class=HTMLResponse)
async def inventory_soon(
    request: Request,
    session: SessionDependency,
    q: str = Query(default=""),
    product_type: str = Query(default=""),
    product_location: str = Query(default=""),
    urgency: str = Query(default="soon"),
    sort: str = Query(default="expiry"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=LIMIT_STEP),
) -> HTMLResponse:
    """Render the urgency-focused inventory page."""
    context = _get_inventory_context(
        request=request,
        session=session,
        q=q,
        product_type=product_type,
        product_location=product_location,
        urgency=urgency,
        sort=sort,
        limit=limit,
        active_nav="soon",
    )
    return templates.TemplateResponse(request=request, name="inventory/index.html", context=context)


@inventory_web_router.get("/web/more", response_class=HTMLResponse)
async def more_page(request: Request) -> HTMLResponse:
    """Render the utility and future-tools screen."""
    return _render_more_page(request)


@inventory_web_router.get(
    "/web/inventory/list", response_class=HTMLResponse, name="render_inventory_list_fragment"
)
async def render_inventory_list_fragment(
    request: Request,
    session: SessionDependency,
    q: str = Query(default=""),
    product_type: str = Query(default=""),
    product_location: str = Query(default=""),
    urgency: str = Query(default="all"),
    sort: str = Query(default="newest"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=LIMIT_STEP),
) -> HTMLResponse:
    """Render the inventory list fragment used by HTMX interactions."""
    context = _get_inventory_context(
        request=request,
        session=session,
        q=q,
        product_type=product_type,
        product_location=product_location,
        urgency=urgency,
        sort=sort,
        limit=limit,
        active_nav="soon" if urgency in {"soon", "expired"} else "inventory",
    )
    return templates.TemplateResponse(
        request=request, name="inventory/_product_list.html", context=context
    )


@inventory_web_router.get("/web/inventory/new", response_class=HTMLResponse)
async def new_product_page(request: Request, return_to: str = Query(default="/")) -> HTMLResponse:
    """Render the add-product page."""
    return _render_form_page(
        request=request,
        title="Add product",
        submit_label="Create product",
        action_url=str(request.url_for("create_product_page")),
        form_data=_empty_form_data(),
        active_nav="add",
        return_to=return_to,
    )


@inventory_web_router.post("/web/inventory", response_class=Response, name="create_product_page")
async def create_product_page(
    request: Request,
    session: SessionDependency,
    product_name: str = Form(default=""),
    description: str = Form(default=""),
    quantity: str = Form(default=""),
    unit: str = Form(default=""),
    expiry_date: str = Form(default=""),
    expiry_date_date: str = Form(default=""),
    product_location: str = Form(default=""),
    product_type: str = Form(default=""),
    return_to: str = Form(default="/"),
) -> Response:
    """Create a product from the mobile form and redirect back home."""
    form_data = _product_from_form(
        product_name=product_name,
        description=description,
        quantity=quantity,
        unit=unit,
        expiry_date=_coalesce_expiry_date(
            expiry_date=expiry_date, expiry_date_date=expiry_date_date
        ),
        product_location=product_location,
        product_type=product_type,
    )
    form_data["expiry_date_date"] = expiry_date_date or form_data["expiry_date"][:10]
    missing_errors = _missing_field_errors(form_data)
    if missing_errors:
        return _render_form_page(
            request=request,
            title="Add product",
            submit_label="Create product",
            action_url=str(request.url_for("create_product_page")),
            form_data=form_data,
            errors=missing_errors,
            active_nav="add",
            return_to=return_to,
        )

    try:
        create_schema = ProductCreate.model_validate(form_data)
        create_schema.validate_against_creation_date(datetime.now(tz=config.brussels_tz))
    except (InvalidExpiryDateError, ValidationError) as exc:
        errors = (
            {"expiry_date": str(exc)}
            if isinstance(exc, InvalidExpiryDateError)
            else _validation_errors(exc)
        )
        return _render_form_page(
            request=request,
            title="Add product",
            submit_label="Create product",
            action_url=str(request.url_for("create_product_page")),
            form_data=form_data,
            errors=errors,
            active_nav="add",
            return_to=return_to,
        )

    try:
        product_crud.create(session=session, obj_in=create_schema)
    except (InvalidProductLocationError, InvalidProductTypeError) as exc:
        return _render_form_page(
            request=request,
            title="Add product",
            submit_label="Create product",
            action_url=str(request.url_for("create_product_page")),
            form_data=form_data,
            errors={"__all__": str(exc)},
            active_nav="add",
            return_to=return_to,
        )

    return _redirect_with_flash(return_to=return_to, message="Product created successfully")


@inventory_web_router.get("/web/inventory/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_page(
    request: Request,
    product_id: int,
    session: SessionDependency,
    return_to: str = Query(default="/web/inventory"),
) -> HTMLResponse:
    """Render the edit page for a single product."""
    product = product_crud.get(session=session, row_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Product not found in the database."
        )

    product_view = ProductRead.from_model(product)
    form_data = _form_data_from_product(product_view)
    form_data["expiry_date"] = format_date_input(product_view.expiry_date)
    return _render_form_page(
        request=request,
        title=f"Edit {product_view.product_name}",
        submit_label="Save changes",
        action_url=str(request.url_for("update_product_page", product_id=product_id)),
        form_data=form_data,
        active_nav="add",
        return_to=return_to,
    )


@inventory_web_router.post(
    "/web/inventory/{product_id}", response_class=Response, name="update_product_page"
)
async def update_product_page(
    request: Request,
    product_id: int,
    session: SessionDependency,
    product_name: str = Form(default=""),
    description: str = Form(default=""),
    quantity: str = Form(default=""),
    unit: str = Form(default=""),
    expiry_date: str = Form(default=""),
    expiry_date_date: str = Form(default=""),
    product_location: str = Form(default=""),
    product_type: str = Form(default=""),
    return_to: str = Form(default="/web/inventory"),
) -> Response:
    """Update a product from the mobile form and redirect back home."""
    product = product_crud.get(session=session, row_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Product not found in the database."
        )

    form_data = _product_from_form(
        product_name=product_name,
        description=description,
        quantity=quantity,
        unit=unit,
        expiry_date=_coalesce_expiry_date(
            expiry_date=expiry_date, expiry_date_date=expiry_date_date
        ),
        product_location=product_location,
        product_type=product_type,
    )
    form_data["expiry_date_date"] = expiry_date_date or form_data["expiry_date"][:10]
    missing_errors = _missing_field_errors(form_data)
    if missing_errors:
        return _render_form_page(
            request=request,
            title=f"Edit {form_data['product_name'] or product.name}",
            submit_label="Save changes",
            action_url=str(request.url_for("update_product_page", product_id=product_id)),
            form_data=form_data,
            errors=missing_errors,
            active_nav="add",
            return_to=return_to,
        )

    try:
        update_schema = ProductUpdate.model_validate(form_data)
        update_schema.validate_against_existing_product(product)
    except (InvalidExpiryDateError, ValidationError) as exc:
        errors = (
            {"expiry_date": str(exc)}
            if isinstance(exc, InvalidExpiryDateError)
            else _validation_errors(exc)
        )
        return _render_form_page(
            request=request,
            title=f"Edit {product.name}",
            submit_label="Save changes",
            action_url=str(request.url_for("update_product_page", product_id=product_id)),
            form_data=form_data,
            errors=errors,
            active_nav="add",
            return_to=return_to,
        )

    try:
        product_crud.update(session=session, row_id=product_id, obj_in=update_schema)
    except (InvalidProductLocationError, InvalidProductTypeError) as exc:
        return _render_form_page(
            request=request,
            title=f"Edit {form_data['product_name']}",
            submit_label="Save changes",
            action_url=str(request.url_for("update_product_page", product_id=product_id)),
            form_data=form_data,
            errors={"__all__": str(exc)},
            active_nav="add",
            return_to=return_to,
        )

    return _redirect_with_flash(return_to=return_to, message="Product updated successfully")


@inventory_web_router.post("/web/inventory/{product_id}/delete", response_class=Response)
async def delete_product_page(
    product_id: int, session: SessionDependency, return_to: str = Form(default="/")
) -> Response:
    """Delete a product from the web UI and redirect back home."""
    product = product_crud.get(session=session, row_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail="Product not found in the database."
        )

    product_crud.remove(session=session, row_id=product.id)
    return _redirect_with_flash(return_to=return_to, message="Product deleted successfully")
