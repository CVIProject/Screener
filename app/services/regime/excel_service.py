from io import BytesIO

from pathlib import Path

from typing import Tuple

import pandas as pd

from openpyxl import load_workbook

from app.core.config import settings


def find_header_row(

    file_path: str

) -> int:

    preview = pd.read_excel(

        file_path,

        header=None,

        nrows=30

    )

    for row_index in range(

        len(
            preview
        )

    ):

        values = [

            str(value).strip()

            for value in preview.iloc[
                row_index
            ].tolist()

        ]

        if (

            settings.DATE_COLUMN
            in
            values

            and

            settings.VALUE_COLUMN
            in
            values

        ):

            return row_index

    raise ValueError(

        "Could not find Excel header row "
        "containing observation_date and "
        "BAMLH0A0HYM2."

    )


def read_workbook_data(

    file_path: str

) -> Tuple[

    pd.DataFrame,

    int,

    str

]:

    header_row = find_header_row(

        file_path

    )

    excel_file = pd.ExcelFile(

        file_path

    )

    sheet_name = (

        excel_file.sheet_names[0]

    )

    df = pd.read_excel(

        file_path,

        sheet_name=sheet_name,

        header=header_row

    )

    df.columns = [

        str(column).strip()

        for column in df.columns

    ]

    if (

        settings.DATE_COLUMN
        not in
        df.columns

    ):

        raise ValueError(

            f"Missing column: "
            f"{settings.DATE_COLUMN}"

        )

    if (

        settings.VALUE_COLUMN
        not in
        df.columns

    ):

        raise ValueError(

            f"Missing column: "
            f"{settings.VALUE_COLUMN}"

        )

    df[
        settings.DATE_COLUMN
    ] = pd.to_datetime(

        df[
            settings.DATE_COLUMN
        ],

        errors="coerce"

    )

    df[
        settings.VALUE_COLUMN
    ] = pd.to_numeric(

        df[
            settings.VALUE_COLUMN
        ],

        errors="coerce"

    )

    df = df.dropna(

        subset=[

            settings.DATE_COLUMN,

            settings.VALUE_COLUMN

        ]

    )

    df = (

        df

        .sort_values(

            settings.DATE_COLUMN

        )

        .reset_index(

            drop=True

        )

    )

    return (

        df,

        header_row,

        sheet_name

    )


def get_last_existing_date(

    df: pd.DataFrame

) -> pd.Timestamp:

    return (

        df[
            settings.DATE_COLUMN
        ]

        .max()

    )

def save_dataframe_to_excel(

    df: pd.DataFrame

) -> BytesIO:

    output = BytesIO()

    # -----------------------------------------
    # Ensure observation_date contains DATE only
    # -----------------------------------------

    if settings.DATE_COLUMN in df.columns:

        df[settings.DATE_COLUMN] = (

            pd.to_datetime(

                df[settings.DATE_COLUMN],

                errors="coerce"

            )

            .dt.date

        )

    # -----------------------------------------
    # Ensure 90-Day Slope has 3 decimals
    # -----------------------------------------

    if settings.SLOPE_COLUMN in df.columns:

        df[settings.SLOPE_COLUMN] = (

            pd.to_numeric(

                df[settings.SLOPE_COLUMN],

                errors="coerce"

            )

            .round(3)

        )

    with pd.ExcelWriter(

        output,

        engine="openpyxl",

        date_format="yyyy-mm-dd",

        datetime_format="yyyy-mm-dd"

    ) as writer:

        df.to_excel(

            writer,

            index=False,

            sheet_name="Regime Data"

        )

        worksheet = (

            writer.sheets[

                "Regime Data"

            ]

        )

        # -----------------------------------------
        # Freeze header row
        # -----------------------------------------

        worksheet.freeze_panes = "A2"

        # -----------------------------------------
        # Enable Excel filter
        # -----------------------------------------

        worksheet.auto_filter.ref = (

            worksheet.dimensions

        )

        # -----------------------------------------
        # Format observation_date
        # -----------------------------------------

        date_column_index = (

            list(df.columns)

            .index(

                settings.DATE_COLUMN

            )

            + 1

        )

        for cell in worksheet.iter_cols(

            min_col=date_column_index,

            max_col=date_column_index,

            min_row=2

        ):

            for date_cell in cell:

                date_cell.number_format = (

                    "yyyy-mm-dd"

                )

        # -----------------------------------------
        # Format 90-Day Slope
        # -----------------------------------------

        slope_column_index = (

            list(df.columns)

            .index(

                settings.SLOPE_COLUMN

            )

            + 1

        )

        for cell in worksheet.iter_cols(

            min_col=slope_column_index,

            max_col=slope_column_index,

            min_row=2

        ):

            for slope_cell in cell:

                slope_cell.number_format = (

                    "0.000"

                )

        # -----------------------------------------
        # Hide columns G, H, I
        # -----------------------------------------

        worksheet.column_dimensions["G"].hidden = True

        worksheet.column_dimensions["H"].hidden = True

        worksheet.column_dimensions["I"].hidden = True

        # -----------------------------------------
        # Auto-size columns
        # -----------------------------------------

        for column_cells in worksheet.columns:

            max_length = 0

            column_letter = (

                column_cells[

                    0

                ].column_letter

            )

            for cell in column_cells:

                if cell.value is not None:

                    max_length = max(

                        max_length,

                        len(

                            str(

                                cell.value

                            )

                        )

                    )

            worksheet.column_dimensions[

                column_letter

            ].width = min(

                max_length + 2,

                50

            )

    output.seek(0)

    return output