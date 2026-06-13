"""Template and static asset helpers for the server-rendered web UI."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from fridge_app_backend.config import ROOT_DIR, config

FRONTEND_DIR = ROOT_DIR.parent / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATE_DIR = FRONTEND_DIR / "templates"


def format_datetime_display(value: datetime) -> str:
    """Format a datetime for compact mobile display."""
    return value.astimezone(config.brussels_tz).strftime("%d %b %Y %H:%M")


def format_date_display(value: datetime | date) -> str:
    """Format a date-like value for user-facing expiry display."""
    if isinstance(value, datetime):
        normalised_value = value.astimezone(config.brussels_tz).date()
    else:
        normalised_value = value
    return normalised_value.strftime("%d %b %Y")


def format_date_input(value: datetime | date) -> str:
    """Format a date-like value for a date form input."""
    if isinstance(value, datetime):
        normalised_value = value.astimezone(config.brussels_tz).date()
    else:
        normalised_value = value
    return normalised_value.strftime("%Y-%m-%d")


def expiry_status(value: datetime) -> str:
    """Return the visual expiry status for a product."""
    current_time = datetime.now(tz=config.brussels_tz)
    normalised_value = value.astimezone(config.brussels_tz)

    if normalised_value < current_time:
        return "expired"
    if normalised_value <= current_time + timedelta(days=3):
        return "expiring-soon"
    return "fresh"


def expiry_status_label(value: datetime) -> str:
    """Return the user-facing label for an expiry status."""
    status = expiry_status(value)
    if status == "expired":
        return "Expired"
    if status == "expiring-soon":
        return "Expiring soon"
    return "Fresh"


_PRODUCT_TYPE_VISUALS: dict[str, dict[str, str]] = {
    "poultry 🍗": {"icon": "fire", "tone": "sunset", "label": "Poultry"},
    "meat 🥩": {"icon": "cube", "tone": "berry", "label": "Meat"},
    "fish 🐟": {"icon": "sparkles", "tone": "ocean", "label": "Fish"},
    "seafood 🍱": {"icon": "circle-stack", "tone": "violet", "label": "Seafood"},
    "vegetable 🥦": {"icon": "shopping-bag", "tone": "garden", "label": "Vegetable"},
    "liquid 💧": {"icon": "beaker", "tone": "sky", "label": "Liquid"},
    "fruit 🍓": {"icon": "sun", "tone": "rose", "label": "Fruit"},
    "dessert 🍨": {"icon": "cake", "tone": "gold", "label": "Dessert"},
    "dairy 🥛": {"icon": "archive-box", "tone": "ice", "label": "Dairy"},
}


def product_type_visual(value: Any) -> dict[str, str]:
    """Return the icon, tone, and simplified label for a product type."""
    raw_value = getattr(value, "value", value)
    return _PRODUCT_TYPE_VISUALS.get(
        str(raw_value), {"icon": "box", "tone": "neutral", "label": str(raw_value).title()}
    )


def product_location_label(value: Any) -> str:
    """Return a compact title-cased label for a product location."""
    raw_value = getattr(value, "value", value)
    return str(raw_value).title()


def product_unit_label(value: Any) -> str:
    """Return the printable unit value instead of Enum repr text."""
    return str(getattr(value, "value", value))


def url_path_for(request: Request, route_name: str, **path_params: object) -> str:
    """Return a local route URL as a path-only value for proxy-safe HTML."""
    return request.url_for(route_name, **path_params).path


templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals.update(
    config=config,
    format_datetime_display=format_datetime_display,
    format_date_display=format_date_display,
    format_date_input=format_date_input,
    expiry_status=expiry_status,
    expiry_status_label=expiry_status_label,
    product_type_visual=product_type_visual,
    product_location_label=product_location_label,
    product_unit_label=product_unit_label,
    url_path_for=url_path_for,
)
