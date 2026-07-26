from datetime import datetime
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.exceptions import (
    ApplicationError,
    CorruptedExcelFileError,
    InvalidExcelDataError,
    MissingColumnsError,
)
from app.services.regime.excel_service import (
    get_last_existing_date,
    read_workbook_data,
    save_dataframe_to_excel,
)
from app.services.regime.fred_service import (
    get_missing_observations,
)
from app.services.regime.regime_service import (
    calculate_new_rows,
)
from app.utils.file_validation import (
    read_and_validate_upload,
)


router = APIRouter(
    prefix="/api/regime",
    tags=["Regime"],
)


@router.post(
    "/continue",
    summary="Continue an existing BAML regime Excel file",
    responses={
        400: {"description": "Invalid file"},
        413: {"description": "File too large"},
        422: {"description": "Invalid Excel structure"},
        502: {"description": "FRED service error"},
        503: {"description": "Network unavailable"},
        504: {"description": "FRED request timed out"},
        500: {"description": "Unexpected server error"},
    },
)
async def continue_regime_excel(
    file: UploadFile = File(...),
):
    content = await read_and_validate_upload(
        file,
        maximum_size_mb=settings.MAX_UPLOAD_SIZE_MB,
    )

    try:
        with TemporaryDirectory() as temporary_directory:
            input_path = (
                Path(temporary_directory)
                / "regime_input.xlsx"
            )

            input_path.write_bytes(content)

            historical_df, _, _ = read_workbook_data(
                str(input_path)
            )

    except ApplicationError:
        raise

    except KeyError as exc:
        missing_column = str(exc).strip("'\"")

        raise MissingColumnsError(
            missing_columns=[missing_column],
            filename=file.filename,
        ) from exc

    except (
        ValueError,
        TypeError,
        pd.errors.ParserError,
    ) as exc:
        message = str(exc)

        if "Missing column" in message:
            missing_column = (
                message.split(":", maxsplit=1)[-1]
                .strip()
            )

            raise MissingColumnsError(
                missing_columns=[missing_column],
                filename=file.filename,
            ) from exc

        raise InvalidExcelDataError(
            message=message,
            user_message=(
                "The regime workbook does not contain the "
                "expected historical data. Check the file "
                "and retry again."
            ),
            details={
                "filename": file.filename,
            },
        ) from exc

    except Exception as exc:
        raise CorruptedExcelFileError(
            filename=file.filename or "regime file",
            technical_message=str(exc),
        ) from exc

    if historical_df.empty:
        raise InvalidExcelDataError(
            message="The regime workbook contains no valid rows.",
            user_message=(
                "The uploaded regime workbook contains no valid data. "
                "Check the file and retry again."
            ),
        )

    last_existing_date = get_last_existing_date(
        historical_df
    )

    new_rows = await get_missing_observations(
        last_existing_date
    )

    if new_rows.empty:
        result_df = historical_df.copy()
        added_rows = 0
    else:
        calculated_rows = calculate_new_rows(
            historical_df,
            new_rows,
        )

        if calculated_rows.empty:
            raise InvalidExcelDataError(
                message=(
                    "New FRED observations were found, but "
                    "no calculated rows were generated."
                ),
                user_message=(
                    "The new regime data could not be calculated. "
                    "Check the uploaded history and retry again."
                ),
            )

        added_rows = len(calculated_rows)

        result_df = pd.concat(
            [
                historical_df,
                calculated_rows,
            ],
            ignore_index=True,
        )

        result_df = (
            result_df
            .sort_values(settings.DATE_COLUMN)
            .drop_duplicates(
                subset=[settings.DATE_COLUMN],
                keep="last",
            )
            .reset_index(drop=True)
        )

    output_file: BytesIO = save_dataframe_to_excel(
        result_df
    )

    output_file.seek(0)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_filename = (
        f"BAML_Regime_Updated_{timestamp}.xlsx"
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
            "X-Added-Rows": str(added_rows),
        },
    )