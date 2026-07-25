from datetime import date

from io import StringIO

import httpx

import pandas as pd

from app.core.config import settings


async def download_fred_data() -> pd.DataFrame:

    async with httpx.AsyncClient(

        timeout=120,

        follow_redirects=True,

        headers={

            "User-Agent":

            "Mozilla/5.0"

        }

    ) as client:

        response = await client.get(

            settings.FRED_CSV_URL

        )

        response.raise_for_status()

        csv_text = response.text

    # ------------------------------------
    # Debugging: inspect returned response
    # ------------------------------------

    print(

        "FRED response first 500 characters:"

    )

    print(

        csv_text[:500]

    )

    # ------------------------------------
    # Read CSV
    # ------------------------------------

    df = pd.read_csv(

        StringIO(

            csv_text

        )

    )

    # ------------------------------------
    # Normalize column names
    # ------------------------------------

    df.columns = [

        str(column)

        .strip()

        .replace(

            "\ufeff",

            ""

        )

        .upper()

        for column in df.columns

    ]

    print(

        "FRED columns received:",

        df.columns.tolist()

    )

    # ------------------------------------
    # Find date column
    # ------------------------------------

    date_column = None

    for column in df.columns:

        if column in [

            "DATE",

            "OBSERVATION_DATE"

        ]:

            date_column = column

            break

    if date_column is None:

        raise ValueError(

            "FRED CSV does not contain "
            "DATE or OBSERVATION_DATE column. "
            f"Received columns: "
            f"{df.columns.tolist()}"

        )

    # ------------------------------------
    # Find BAML value column
    # ------------------------------------

    value_column = None

    for column in df.columns:

        if (

            column.upper()

            ==

            "BAMLH0A0HYM2"

        ):

            value_column = column

            break

    if value_column is None:

        raise ValueError(

            "FRED CSV does not contain "
            "BAMLH0A0HYM2 column. "
            f"Received columns: "
            f"{df.columns.tolist()}"

        )

    # ------------------------------------
    # Rename columns
    # ------------------------------------

    df = df.rename(

        columns={

            date_column:

            settings.DATE_COLUMN,

            value_column:

            settings.VALUE_COLUMN

        }

    )

    # ------------------------------------
    # Parse dates
    # ------------------------------------

    df[

        settings.DATE_COLUMN

    ] = pd.to_datetime(

        df[

            settings.DATE_COLUMN

        ],

        errors="coerce"

    )

    # ------------------------------------
    # Parse numeric values
    # ------------------------------------

    df[

        settings.VALUE_COLUMN

    ] = pd.to_numeric(

        df[

            settings.VALUE_COLUMN

        ],

        errors="coerce"

    )

    # ------------------------------------
    # Remove invalid rows
    # ------------------------------------

    df = df.dropna(

        subset=[

            settings.DATE_COLUMN,

            settings.VALUE_COLUMN

        ]

    )

    # ------------------------------------
    # Sort and remove duplicates
    # ------------------------------------

    df = (

        df

        .sort_values(

            settings.DATE_COLUMN

        )

        .drop_duplicates(

            subset=[

                settings.DATE_COLUMN

            ],

            keep="last"

        )

        .reset_index(

            drop=True

        )

    )

    return df


async def get_missing_observations(

    last_existing_date: pd.Timestamp

) -> pd.DataFrame:

    fred_df = await (

        download_fred_data()

    )

    yesterday = (

        pd.Timestamp(

            date.today()

        )

        -

        pd.Timedelta(

            days=1

        )

    )

    missing = fred_df[

        (

            fred_df[

                settings.DATE_COLUMN

            ]

            >

            last_existing_date

        )

        &

        (

            fred_df[

                settings.DATE_COLUMN

            ]

            <=

            yesterday

        )

    ].copy()

    return (

        missing

        .sort_values(

            settings.DATE_COLUMN

        )

        .reset_index(

            drop=True

        )

    )