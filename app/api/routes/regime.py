from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.services.regime.excel_service import (
    read_historical_workbook,
    read_new_values_workbook,
    save_dataframe_to_excel,
)
from app.services.regime.regime_service import (
    append_new_observations,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/regime",
    tags=["Regime"],
)


ALLOWED_EXCEL_EXTENSIONS = {
    ".xlsx",
    ".xlsm",
}


async def validate_excel_upload(
    upload_file: UploadFile,
    description: str,
) -> bytes:
    """
    Validate and read an uploaded Excel file.
    """
    filename = upload_file.filename or ""

    if not filename:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MISSING_FILENAME",
                "message": (
                    f"{description} does not have a filename."
                ),
                "user_message": (
                    f"Select a valid {description} and retry again."
                ),
            },
        )

    extension = Path(
        filename
    ).suffix.lower()

    if extension not in ALLOWED_EXCEL_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": (
                    f"{description} has unsupported extension "
                    f"'{extension}'."
                ),
                "user_message": (
                    f"{description} must be an .xlsx or .xlsm file."
                ),
            },
        )

    try:
        content = await upload_file.read()
    except Exception as exc:
        logger.exception(
            "Unable to read uploaded file: %s",
            filename,
        )

        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_READ_ERROR",
                "message": str(exc),
                "user_message": (
                    f"Unable to read {description}. "
                    "Check the file and retry again."
                ),
            },
        ) from exc

    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_FILE",
                "message": (
                    f"{description} is empty."
                ),
                "user_message": (
                    f"{description} is empty. "
                    "Select a valid file and retry again."
                ),
            },
        )

    maximum_size_bytes = (
        settings.MAX_UPLOAD_SIZE_MB
        * 1024
        * 1024
    )

    if len(content) > maximum_size_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": (
                    f"{description} exceeds the "
                    f"{settings.MAX_UPLOAD_SIZE_MB} MB limit."
                ),
                "user_message": (
                    f"{description} must be smaller than "
                    f"{settings.MAX_UPLOAD_SIZE_MB} MB."
                ),
            },
        )

    # XLSX and XLSM are ZIP-based formats and normally start with PK.
    if not content.startswith(b"PK"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EXCEL_FILE",
                "message": (
                    f"{description} is not a valid Office Open XML "
                    "Excel workbook."
                ),
                "user_message": (
                    f"{description} is corrupted or is not a valid "
                    "Excel file. Check the file and retry again."
                ),
            },
        )

    return content


@router.post(
    "/append",
    summary=(
        "Append new BAML observations to a historical regime workbook"
    ),
    responses={
        200: {
            "description": (
                "Updated historical regime Excel workbook"
            )
        },
        400: {
            "description": (
                "Invalid upload or no new rows"
            )
        },
        413: {
            "description": (
                "Uploaded file exceeds the size limit"
            )
        },
        422: {
            "description": (
                "Excel workbook structure or data is invalid"
            )
        },
        500: {
            "description": (
                "Unexpected regime processing error"
            )
        },
    },
)
async def append_regime_files(
    new_values_file: UploadFile = File(
        ...,
        description=(
            'Excel workbook containing a "Daily, Close" sheet '
            "with observation_date and BAMLH0A0HYM2 columns."
        ),
    ),
    historical_file: UploadFile = File(
        ...,
        description=(
            "Historical regime Excel workbook containing columns A-K."
        ),
    ),
):
    """
    Process two Excel workbooks:

    1. New-values workbook:
       - Reads only the sheet named 'Daily, Close'.
       - Uses observation_date and BAMLH0A0HYM2.

    2. Historical regime workbook:
       - Uses the existing calculated columns A-K.
       - Ignores extra columns.

    All missing observations are calculated sequentially and appended.
    """
    logger.info(
        "Regime append request started. "
        "new_values_file=%s historical_file=%s",
        new_values_file.filename,
        historical_file.filename,
    )

    new_values_content = await validate_excel_upload(
        new_values_file,
        "New BAML values file",
    )

    historical_content = await validate_excel_upload(
        historical_file,
        "Historical regime file",
    )

    try:
        new_values_dataframe = (
            read_new_values_workbook(
                new_values_content
            )
        )

        logger.info(
            "New-values workbook loaded. "
            "rows=%s first_date=%s last_date=%s",
            len(new_values_dataframe),
            new_values_dataframe[
                settings.DATE_COLUMN
            ].min(),
            new_values_dataframe[
                settings.DATE_COLUMN
            ].max(),
        )

        historical_dataframe = (
            read_historical_workbook(
                historical_content
            )
        )

        logger.info(
            "Historical workbook loaded. "
            "rows=%s latest_date=%s",
            len(historical_dataframe),
            historical_dataframe[
                settings.DATE_COLUMN
            ].max(),
        )

        result_dataframe, appended_dataframe = (
            append_new_observations(
                historical_df=historical_dataframe,
                new_values_df=new_values_dataframe,
            )
        )

        logger.info(
            "Regime calculations completed. "
            "appended_rows=%s",
            len(appended_dataframe),
        )

        output_file = save_dataframe_to_excel(
            result_dataframe
        )

    except ValueError as exc:
        logger.warning(
            "Regime validation failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=422,
            detail={
                "code": "REGIME_VALIDATION_ERROR",
                "message": str(exc),
                "user_message": (
                    f"{exc} Check the uploaded files and retry again."
                ),
            },
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected regime processing error."
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "REGIME_PROCESSING_ERROR",
                "message": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "user_message": (
                    "The regime workbook could not be processed. "
                    "Check the files and retry again."
                ),
            },
        ) from exc

    if appended_dataframe.empty:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_NEW_ROWS",
                "message": (
                    "No new observations were appended."
                ),
                "user_message": (
                    "No new observations were found. "
                    "Check the dates and retry again."
                ),
            },
        )

    first_appended_date = (
        appended_dataframe[
            settings.DATE_COLUMN
        ]
        .min()
        .date()
        .isoformat()
    )

    last_appended_date = (
        appended_dataframe[
            settings.DATE_COLUMN
        ]
        .max()
        .date()
        .isoformat()
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_filename = (
        f"BAML_Regime_Updated_{timestamp}.xlsx"
    )

    logger.info(
        "Regime append request completed. "
        "appended_rows=%s first_date=%s last_date=%s",
        len(appended_dataframe),
        first_appended_date,
        last_appended_date,
    )

    return StreamingResponse(
        output_file,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{output_filename}"'
            ),
            "X-Appended-Rows": str(
                len(appended_dataframe)
            ),
            "X-First-Appended-Date":
                first_appended_date,
            "X-Last-Appended-Date":
                last_appended_date,
        },
    )