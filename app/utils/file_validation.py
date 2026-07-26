from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
)


EXCEL_EXTENSIONS = {
    ".xlsx",
    ".xlsm",
}


async def read_and_validate_upload(
    upload_file: UploadFile,
    *,
    maximum_size_mb: int,
    allowed_extensions: set[str] | None = None,
) -> bytes:
    allowed_extensions = (
        allowed_extensions or EXCEL_EXTENSIONS
    )

    filename = upload_file.filename or ""
    extension = Path(filename).suffix.lower()

    if not filename or extension not in allowed_extensions:
        raise InvalidFileTypeError(
            filename=filename or "unnamed file",
            allowed_extensions=allowed_extensions,
        )

    content = await upload_file.read()

    if not content:
        raise EmptyFileError(filename)

    maximum_bytes = maximum_size_mb * 1024 * 1024

    if len(content) > maximum_bytes:
        raise FileTooLargeError(
            filename=filename,
            maximum_size_mb=maximum_size_mb,
        )

    # XLSX and XLSM files are ZIP-based and normally begin with PK.
    if not content.startswith(b"PK"):
        raise InvalidFileTypeError(
            filename=filename,
            allowed_extensions=allowed_extensions,
        )

    return content