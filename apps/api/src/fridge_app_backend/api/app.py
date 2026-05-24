"""Main entrypoint for the API."""

import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_400_BAD_REQUEST

from fridge_app_backend.api.routes.inventory_routes import inventory_router
from fridge_app_backend.api.routes.utils_routes import utils_router
from fridge_app_backend.config import config
from fridge_app_backend.exceptions import (
    InvalidExpiryDateError,
    InvalidProductLocationError,
    InvalidProductTypeError,
)
from fridge_app_backend.orm.database import initialise_db
from fridge_app_backend.web.routes import inventory_web_router
from fridge_app_backend.web.templating import STATIC_DIR

logger = logging.getLogger(__name__)
logger.info("Running COMMIT", extra={"commit": config.commit_sha})


logging.basicConfig()
logging.getLogger("root").setLevel(logging.INFO)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialize and close the database connection."""
    logger.info("API start up operations...")
    logger.info("Initialising DB...")

    if config.db_type == "in_memory":
        initialise_db()
    elif config.db_type == "postgres":
        logger.info("Using persistent postgres database.")
    else:
        raise NotImplementedError("Only in_memory sqlite and postgres supported for now")

    try:
        yield  # Yield control to the application
        logger.info("API shut down operations...")

    finally:
        # Close the database connection
        pass


app = FastAPI(
    title=f"{config.api_name} in {config.environment} environment with {config.db_type} database",
    description=config.api_description,
    started=datetime.now(tz=config.brussels_tz),
    version=config.api_version,
    root_path=config.api_root_path,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(inventory_router)
app.include_router(utils_router)
app.include_router(inventory_web_router)


# Exception handlers for validation errors
@app.exception_handler(InvalidProductTypeError)
async def invalid_product_type_handler(
    request: Request, exc: InvalidProductTypeError
) -> JSONResponse:
    """Handle InvalidProductTypeError by returning HTTP 400."""
    return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(InvalidProductLocationError)
async def invalid_product_location_handler(
    request: Request, exc: InvalidProductLocationError
) -> JSONResponse:
    """Handle InvalidProductLocationError by returning HTTP 400."""
    return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(InvalidExpiryDateError)
async def invalid_expiry_date_handler(
    request: Request, exc: InvalidExpiryDateError
) -> JSONResponse:
    """Handle InvalidExpiryDateError by returning HTTP 400."""
    return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.middleware("http")
async def add_headers(request: Request, call_next: Callable[..., Any]) -> Response:
    """
    Add process time and security headers.

    Middleware to add extra headers to report the time required to execute
    an API call and several security headers.
    """
    start_time = datetime.now(tz=config.brussels_tz)
    response: Response = await call_next(request)
    process_time = datetime.now(tz=config.brussels_tz) - start_time

    # Inject security headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "sameorigin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/index", include_in_schema=False)
async def index() -> dict[str, str | list[str]]:
    """Index API Call."""
    return {
        "Title": app.title,
        "Description": app.description,
        "started": app.extra["started"].isoformat(),
        "Git commit": os.environ.get("COMMIT", "not set"),
        "Git branch": os.environ.get("BRANCH", "not set"),
    }
