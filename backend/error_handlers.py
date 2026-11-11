import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

FIELD_MESSAGES = {
    "email": "Enter a valid email address.",
    "password": "Password must meet the minimum length requirement.",
    "title": "Title is required and must be no longer than 120 characters.",
    "description": "Description is required.",
}


def _safe_validation_details(error: RequestValidationError) -> list[dict[str, Any]]:
    details = []
    for issue in error.errors():
        location = [str(part) for part in issue.get("loc", ())]
        field = location[-1] if location else "request"
        details.append(
            {
                "loc": location,
                "msg": FIELD_MESSAGES.get(field, "Check this field and try again."),
                "type": "value_error",
            }
        )
    return details


async def validation_error_handler(_request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _safe_validation_details(error)})


async def unexpected_error_handler(_request: Request, error: Exception) -> JSONResponse:
    logger.error("Unhandled API failure (%s)", type(error).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


def install_api_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
