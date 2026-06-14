"""Runtime deployment metadata helpers."""

import os
import socket
from datetime import datetime

from fastapi import Request
from pydantic import BaseModel

from fridge_app_backend.config import config

UNKNOWN = "unknown"


class DeploymentInfo(BaseModel):
    """Public runtime and deployment metadata."""

    image_ref: str
    image_digest: str
    deployed_at: str
    app_started_at: datetime
    uptime_seconds: int
    uptime_label: str
    api_version: str
    environment: str
    db_type: str
    root_path: str
    commit: str
    branch: str
    host_name: str
    docs_url: str
    deployment_info_url: str


def _path_with_root(root_path: str, path: str) -> str:
    """Prefix a route path with the current mounted root path."""
    clean_root = root_path.rstrip("/")
    if clean_root:
        return f"{clean_root}{path}"
    return path


def _format_duration(seconds: int) -> str:
    """Return a compact human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"

    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours, remaining_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {remaining_minutes}m"

    days, remaining_hours = divmod(hours, 24)
    return f"{days}d {remaining_hours}h"


def _normalise_started_at(value: object, fallback: datetime) -> datetime:
    """Return a timezone-aware app start time."""
    if not isinstance(value, datetime):
        return fallback
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return config.brussels_tz.localize(value)
    return value.astimezone(config.brussels_tz)


def get_deployment_info(request: Request) -> DeploymentInfo:
    """Build public deployment metadata for API and server-rendered UI consumers."""
    now = datetime.now(tz=config.brussels_tz)
    app_started_at = _normalise_started_at(request.app.extra.get("started"), fallback=now)
    uptime_seconds = max(0, int((now - app_started_at).total_seconds()))
    root_path = str(request.scope.get("root_path") or config.api_root_path or "")

    return DeploymentInfo(
        image_ref=os.getenv("IMAGE_REF", UNKNOWN),
        image_digest=os.getenv("IMAGE_DIGEST", UNKNOWN),
        deployed_at=os.getenv("DEPLOYED_AT", UNKNOWN),
        app_started_at=app_started_at,
        uptime_seconds=uptime_seconds,
        uptime_label=_format_duration(uptime_seconds),
        api_version=config.api_version,
        environment=config.environment,
        db_type=config.db_type,
        root_path=root_path or "/",
        commit=os.getenv("COMMIT", UNKNOWN),
        branch=os.getenv("BRANCH", UNKNOWN),
        host_name=socket.gethostname() or UNKNOWN,
        docs_url=_path_with_root(root_path, "/docs"),
        deployment_info_url=_path_with_root(root_path, "/utils/deployment"),
    )
