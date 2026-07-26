from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl.utils.exceptions import InvalidFileException

from app.core.config import settings
from app.core.exceptions import (
    ApplicationError,
    CorruptedExcelFileError,
    ExternalServiceNetworkError,
    InvalidExcelDataError,
    MissingColumnsError,
)
from app.services.screener.screening_service import (
    process_excel,
)
from app.utils.file_validation import (
    read_and_validate_upload,
)


router = APIRouter(
    prefix="/api/screener",
    tags=["Stock Screener"],
)


@router.post(
    "/filter",
    summary="Filter and rank uploaded stocks",
    responses={
        400: {"description": "Invalid file"},
        413: {"description": "File too large"},
        422: {"description": "Invalid Excel structure"},
        503: {"description": "Market-data network error"},
        504: {"description": "Market-data timeout"},
        500: {"description": "Unexpected server error"},
    },
)
async def filter_stocks(
    stock_file: UploadFile = File(...),
    biblical_file: UploadFile = File(...),
):
    max_upload_size_mb = getattr(
        settings,
        "MAX_UPLOAD_SIZE_MB",
        10,
    )

    stock_content = await read_and_validate_upload(
        stock_file,
        maximum_size_mb=max_upload_size_mb,
    )

    biblical_content = await read_and_validate_upload(
        biblical_file,
        maximum_size_mb=max_upload_size_mb,
    )

    try:
        with TemporaryDirectory() as temporary_directory:
            temporary_path = Path(
                temporary_directory
            )

            stock_path = (
                temporary_path / "stock_input.xlsx"
            )
            biblical_path = (
                temporary_path / "biblical_input.xlsx"
            )
            output_path = (
                temporary_path / "screener_result.xlsx"
            )

            stock_path.write_bytes(stock_content)
            biblical_path.write_bytes(
                biblical_content
            )

            process_excel(
                str(stock_path),
                str(biblical_path),
                str(output_path),
            )

            if not output_path.exists():
                raise InvalidExcelDataError(
                    message=(
                        "The screener did not create an output file."
                    ),
                    user_message=(
                        "The screening process completed without "
                        "creating a result. Check the uploaded files "
                        "and retry again."
                    ),
                )

            output_content = output_path.read_bytes()

    except ApplicationError:
        raise

    except KeyError as exc:
        column_name = str(exc).strip("'\"")

        raise MissingColumnsError(
            missing_columns=[column_name],
            filename=stock_file.filename,
        ) from exc

    except InvalidFileException as exc:
        raise CorruptedExcelFileError(
            filename=stock_file.filename or "stock file",
            technical_message=str(exc),
        ) from exc

    except (
        ValueError,
        TypeError,
        pd.errors.ParserError,
    ) as exc:
        raise InvalidExcelDataError(
            message=str(exc),
            user_message=(
                "One of the uploaded Excel files contains "
                "invalid values or an unexpected format. "
                "Check both files and retry again."
            ),
            details={
                "stock_file": stock_file.filename,
                "biblical_file": biblical_file.filename,
            },
        ) from exc

    except (
        ConnectionError,
        TimeoutError,
    ) as exc:
        raise ExternalServiceNetworkError(
            service_name="Yahoo Finance",
            technical_message=str(exc),
        ) from exc

    except Exception as exc:
        error_text = str(exc).lower()

        network_terms = (
            "connection",
            "network",
            "timed out",
            "timeout",
            "dns",
            "name resolution",
            "temporary failure",
            "failed to connect",
        )

        if any(
            term in error_text
            for term in network_terms
        ):
            raise ExternalServiceNetworkError(
                service_name="Yahoo Finance",
                technical_message=str(exc),
            ) from exc

        raise

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_filename = (
        f"filtered_file_{timestamp}.xlsx"
    )

    return StreamingResponse(
        BytesIO(output_content),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{output_filename}"'
            ),
        },
    )