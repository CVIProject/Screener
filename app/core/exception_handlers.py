import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.exceptions import ApplicationError


logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    return getattr(
        request.state,
        "request_id",
        str(uuid.uuid4()),
    )


def build_error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    user_message: str,
    details: Any = None,
) -> JSONResponse:
    request_id = get_request_id(request)

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "user_message": user_message,
                "details": details,
            },
            "request_id": request_id,
            "path": request.url.path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers={
            "X-Request-ID": request_id,
        },
    )


async def application_error_handler(
    request: Request,
    exception: ApplicationError,
) -> JSONResponse:
    logger.warning(
        "Application error request_id=%s path=%s code=%s message=%s",
        get_request_id(request),
        request.url.path,
        exception.code,
        exception.message,
    )

    return build_error_response(
        request=request,
        status_code=exception.status_code,
        code=exception.code,
        message=exception.message,
        user_message=exception.user_message,
        details=exception.details,
    )


async def request_validation_error_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    validation_errors = []

    for error in exception.errors():
        validation_errors.append(
            {
                "field": ".".join(
                    str(value)
                    for value in error.get("loc", [])
                ),
                "message": error.get("msg"),
                "type": error.get("type"),
            }
        )

    return build_error_response(
        request=request,
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        user_message=(
            "Some required information is missing or invalid. "
            "Check the selected files and retry again."
        ),
        details=validation_errors,
    )


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    detail = exception.detail

    if exception.status_code == 404:
        return build_error_response(
            request=request,
            status_code=404,
            code=ErrorCode.ENDPOINT_NOT_FOUND,
            message="The requested endpoint was not found.",
            user_message="The requested operation could not be found.",
        )

    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        message = detail.get("message", str(detail))
        user_message = detail.get(
            "user_message",
            "The request could not be completed.",
        )
        details = detail.get("details")
    else:
        code = "HTTP_ERROR"
        message = str(detail)
        user_message = str(detail)
        details = None

    return build_error_response(
        request=request,
        status_code=exception.status_code,
        code=code,
        message=message,
        user_message=user_message,
        details=details,
    )


async def unexpected_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    request_id = get_request_id(request)

    logger.exception(
        "Unexpected error request_id=%s path=%s",
        request_id,
        request.url.path,
        exc_info=exception,
    )

    return build_error_response(
        request=request,
        status_code=500,
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        message="An unexpected server error occurred.",
        user_message=(
            "Something went wrong while processing your request. "
            "Check the file and retry again. "
            f"Reference ID: {request_id}"
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        ApplicationError,
        application_error_handler,
    )

    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )

    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )

    app.add_exception_handler(
        Exception,
        unexpected_exception_handler,
    )