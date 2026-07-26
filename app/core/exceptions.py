from typing import Any

from app.core.error_codes import ErrorCode


class ApplicationError(Exception):
    """Base exception for errors safe to return to the frontend."""

    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode | str,
        message: str,
        user_message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.code = str(code)
        self.message = message
        self.user_message = user_message
        self.details = details


class InvalidFileTypeError(ApplicationError):
    def __init__(
        self,
        filename: str,
        allowed_extensions: set[str],
    ) -> None:
        extensions = ", ".join(sorted(allowed_extensions))

        super().__init__(
            status_code=400,
            code=ErrorCode.INVALID_FILE_TYPE,
            message=(
                f"Unsupported file type for '{filename}'. "
                f"Allowed extensions: {extensions}"
            ),
            user_message=(
                f"The selected file is not supported. "
                f"Upload one of these file types: {extensions}."
            ),
            details={
                "filename": filename,
                "allowed_extensions": sorted(allowed_extensions),
            },
        )


class EmptyFileError(ApplicationError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            status_code=400,
            code=ErrorCode.EMPTY_FILE,
            message=f"The uploaded file '{filename}' is empty.",
            user_message=(
                "The uploaded file is empty. "
                "Select a valid Excel file and retry again."
            ),
            details={"filename": filename},
        )


class FileTooLargeError(ApplicationError):
    def __init__(
        self,
        filename: str,
        maximum_size_mb: int,
    ) -> None:
        super().__init__(
            status_code=413,
            code=ErrorCode.FILE_TOO_LARGE,
            message=(
                f"The file '{filename}' exceeds the "
                f"{maximum_size_mb} MB upload limit."
            ),
            user_message=(
                f"The uploaded file is too large. "
                f"The maximum allowed size is {maximum_size_mb} MB."
            ),
            details={
                "filename": filename,
                "maximum_size_mb": maximum_size_mb,
            },
        )


class CorruptedExcelFileError(ApplicationError):
    def __init__(
        self,
        filename: str,
        technical_message: str | None = None,
    ) -> None:
        super().__init__(
            status_code=422,
            code=ErrorCode.CORRUPTED_EXCEL_FILE,
            message=(
                technical_message
                or f"Unable to read Excel workbook '{filename}'."
            ),
            user_message=(
                "The Excel file could not be read. It may be corrupted, "
                "password-protected, or incorrectly formatted. "
                "Check the file and retry again."
            ),
            details={"filename": filename},
        )


class MissingColumnsError(ApplicationError):
    def __init__(
        self,
        missing_columns: list[str],
        filename: str | None = None,
    ) -> None:
        column_text = ", ".join(missing_columns)

        super().__init__(
            status_code=422,
            code=ErrorCode.MISSING_REQUIRED_COLUMNS,
            message=f"Missing required columns: {column_text}",
            user_message=(
                f"The uploaded file is missing required columns: "
                f"{column_text}. Check the file and retry again."
            ),
            details={
                "filename": filename,
                "missing_columns": missing_columns,
            },
        )


class InvalidExcelDataError(ApplicationError):
    def __init__(
        self,
        message: str,
        user_message: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(
            status_code=422,
            code=ErrorCode.INVALID_EXCEL_DATA,
            message=message,
            user_message=(
                user_message
                or "The Excel file contains invalid or incomplete data. "
                "Check the file and retry again."
            ),
            details=details,
        )


class ExternalServiceTimeoutError(ApplicationError):
    def __init__(self, service_name: str) -> None:
        super().__init__(
            status_code=504,
            code=ErrorCode.EXTERNAL_SERVICE_TIMEOUT,
            message=f"{service_name} request timed out.",
            user_message=(
                f"{service_name} is taking too long to respond. "
                "Please check your internet connection and retry again."
            ),
            details={"service": service_name},
        )


class ExternalServiceNetworkError(ApplicationError):
    def __init__(
        self,
        service_name: str,
        technical_message: str | None = None,
    ) -> None:
        super().__init__(
            status_code=503,
            code=ErrorCode.NETWORK_ERROR,
            message=(
                technical_message
                or f"Unable to connect to {service_name}."
            ),
            user_message=(
                f"Unable to connect to {service_name}. "
                "Check your network connection and retry again."
            ),
            details={"service": service_name},
        )


class ExternalServiceError(ApplicationError):
    def __init__(
        self,
        service_name: str,
        technical_message: str | None = None,
    ) -> None:
        super().__init__(
            status_code=502,
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            message=(
                technical_message
                or f"{service_name} returned an unsuccessful response."
            ),
            user_message=(
                f"{service_name} is temporarily unavailable. "
                "Please retry again after some time."
            ),
            details={"service": service_name},
        )