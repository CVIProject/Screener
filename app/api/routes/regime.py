from datetime import datetime

from pathlib import Path

from fastapi import APIRouter

from fastapi import File

import pandas as pd

from fastapi import UploadFile

from fastapi.responses import StreamingResponse

from app.services.regime.excel_service import (

    read_workbook_data,

    get_last_existing_date,

    save_dataframe_to_excel

)

from app.services.regime.fred_service import (

    get_missing_observations

)

from app.services.regime.regime_service import (

    calculate_new_rows

)

from app.core.config import settings


router = APIRouter(

    prefix="/api/regime",

    tags=[

        "Regime"

    ]

)


@router.post(

    "/continue",

    summary=(

        "Continue existing BAML regime Excel file"

    )

)

async def continue_regime_excel(

    file: UploadFile = File(...)

):

    if not file.filename:

        raise ValueError(

            "Uploaded file must have a filename."

        )

    if not file.filename.lower().endswith(

        (

            ".xlsx",

            ".xlsm"

        )

    ):

        raise ValueError(

            "Only .xlsx and .xlsm files "
            "are supported."

        )

    input_path = (

        settings.DATA_DIR

        /

        (

            "uploaded_"

            +

            file.filename

        )

    )

    content = await file.read()

    input_path.write_bytes(

        content

    )

    # -------------------------------
    # Read existing workbook
    # -------------------------------

    historical_df, header_row, sheet_name = (

        read_workbook_data(

            str(

                input_path

            )

        )

    )

    last_existing_date = (

        get_last_existing_date(

            historical_df

        )

    )

    # -------------------------------
    # Download new public FRED data
    # -------------------------------

    new_rows = await (

        get_missing_observations(

            last_existing_date

        )

    )

    if new_rows.empty:

        result_df = historical_df.copy()

        message = (

            "No new FRED observations "
            "were available through yesterday."

        )

    else:

        # -------------------------------
        # Calculate only new continuation
        # -------------------------------

        calculated_rows = (

            calculate_new_rows(

                historical_df,

                new_rows

            )

        )

        # -------------------------------
        # Append to historical workbook
        # -------------------------------

        result_df = pd.concat(

            [

                historical_df,

                calculated_rows

            ],

            ignore_index=True

        )

        result_df = (

            result_df

            .sort_values(

                settings.DATE_COLUMN

            )

            .reset_index(

                drop=True

            )

        )

        message = (

            f"Added {len(calculated_rows)} "
            f"new observations."

        )

    # -------------------------------
    # Create output Excel
    # -------------------------------

    output_file = (

        save_dataframe_to_excel(

            result_df

        )

    )

    timestamp = datetime.now().strftime(

        "%Y%m%d_%H%M%S"

    )

    output_filename = (

        f"BAML_Regime_Updated_"

        f"{timestamp}.xlsx"

    )

    return StreamingResponse(

        output_file,

        media_type=(

            "application/vnd.openxmlformats-officedocument"

            ".spreadsheetml.sheet"

        ),

        headers={

            "Content-Disposition":

            (

                "attachment; "

                f'filename="{output_filename}"'

            ),

            "X-Last-Existing-Date":

            str(

                last_existing_date.date()

            ),

            "X-New-Rows":

            str(

                len(

                    new_rows

                )

            )

        }

    )