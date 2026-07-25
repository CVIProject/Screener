from typing import Optional

import numpy as np

import pandas as pd

from app.core.config import settings


def excel_slope(

    values: pd.Series

) -> float:

    """

    Equivalent to Excel:

        =SLOPE(y_range, x_range)

    where x is:

        1, 2, 3, ..., N

    """

    clean_values = (

        pd.to_numeric(

            values,

            errors="coerce"

        )

        .dropna()

        .astype(float)

    )

    if len(

        clean_values

    ) < 2:

        return np.nan

    x = np.arange(

        1,

        len(
            clean_values
        )

        + 1

    )

    y = (

        clean_values

        .to_numpy()

    )

    slope = np.polyfit(

        x,

        y,

        1

    )[0]

    return round(

        float(
            slope
        ),

        3

    )


def calculate_90_day_slope(

    values: pd.Series

) -> float:

    """

    Your workbook's rolling SLOPE window.

    The workbook uses the current row plus
    the preceding rolling rows.

    The effective historical formula is
    continued using the same rolling range.

    """

    # 87 previous rows + current row
    window_size = 87

    window = (

        values

        .iloc[

            max(

                0,

                len(
                    values
                )

                -

                window_size

                +

                1

            ):

        ]

    )

    return excel_slope(

        window

    )


def calculate_90_day_median(

    values: pd.Series

) -> float:

    """

    Exact continuation of:

        =MEDIAN(B7717:B7805)

    The workbook uses the rolling
    historical observation window.

    """

    window_size = 89

    window = (

        values

        .iloc[

            max(

                0,

                len(
                    values
                )

                -

                window_size

            ):

        ]

    )

    return round(

        float(

            window

            .median()

        ),

        2

    )


def calculate_10_year_median(

    values: pd.Series

) -> float:

    """

    Continuation of the existing workbook's
    rolling 10-year median range.

    Existing workbook formula:

        =MEDIAN(B5207:B7805)

    This is a 2,599-row historical range.

    """

    window_size = 2599

    window = (

        values

        .iloc[

            max(

                0,

                len(
                    values
                )

                -

                window_size

            ):

        ]

    )

    return round(

        float(

            window

            .median()

        ),

        2

    )


def classify_quad(

    current_value: float,

    median_90: float,

    median_10_year: float

) -> str:

    """

    Exact workbook logic:

    B > D and B > E
        recession QAD 4

    B > D and B < E
        Recovery  QAD 1

    B < D and B > E
        Overheating QAD 3

    Otherwise
        Growth QAD 2

    """

    if (

        current_value
        >
        median_90

        and

        current_value
        >
        median_10_year

    ):

        return "recession QAD 4"

    if (

        current_value
        >
        median_90

        and

        current_value
        <
        median_10_year

    ):

        return "Recovery  QAD 1"

    if (

        current_value
        <
        median_90

        and

        current_value
        >
        median_10_year

    ):

        return "Overheating QAD 3"

    return "Growth QAD 2"


def get_qad_value(

    quad: str

) -> Optional[int]:

    mapping = {

        "Growth QAD 2": 2,

        "Recovery  QAD 1": 1,

        "recession QAD 4": 4,

        "Overheating QAD 3": 3

    }

    return mapping.get(

        quad

    )


def calculate_3_day_rule(

    quad_history: list[str],

    previous_rule: Optional[str]

) -> str:

    if len(

        quad_history

    ) < 3:

        return (

            previous_rule
            or
            quad_history[-1]

        )

    last_three = (

        quad_history[-3:]

    )

    if (

        last_three[0]
        ==
        last_three[1]
        ==
        last_three[2]

    ):

        return last_three[-1]

    return (

        previous_rule
        or
        last_three[-1]

    )


def mode_value(

    values: list[int]

) -> Optional[int]:

    if not values:

        return None

    counts = {}

    for value in values:

        counts[value] = (

            counts.get(

                value,

                0

            )

            + 1

        )

    max_count = max(

        counts.values()

    )

    candidates = [

        value

        for value,

        count

        in counts.items()

        if count == max_count

    ]

    # Excel MODE behavior is not
    # reliably defined for ties.
    #
    # We use the most recent tied value.
    for value in reversed(values):

        if value in candidates:

            return value

    return candidates[0]


def calculate_7_day_rule(

    qad_history: list[int],

    previous_rule: Optional[int]

) -> Optional[int]:

    if len(

        qad_history

    ) < 7:

        return (

            previous_rule
            or
            qad_history[-1]

        )

    last_seven = (

        qad_history[-7:]

    )

    return mode_value(

        last_seven

    )


def calculate_confirmed_regime(

    quad_history: list[str],

    previous_confirmed: Optional[str]

) -> Optional[str]:

    """

    New signal must appear five consecutive
    times before the confirmed regime changes.

    Equivalent to:

        COUNTIF(last five, current) = 5

    and current != previous confirmed signal.

    """

    current = quad_history[-1]

    if (

        current is None

        or

        current == ""

    ):

        return previous_confirmed

    if previous_confirmed is None:

        return current

    if current == previous_confirmed:

        return previous_confirmed

    if len(

        quad_history

    ) < settings.CONFIRM_DAYS:

        return previous_confirmed

    last_five = (

        quad_history[

            -settings.CONFIRM_DAYS:

        ]

    )

    if (

        len(

            last_five

        )

        ==

        settings.CONFIRM_DAYS

        and

        all(

            value == current

            for value in last_five

        )

    ):

        return current

    return previous_confirmed


def calculate_trade_regime(

    quad_history: list[str],

    previous_trade: Optional[str]

) -> Optional[str]:

    """

    New regime must satisfy:

    1. Current signal appears for
       five consecutive rows.

    2. Current signal appears at least
       nine times in the latest 15 rows.

    """

    current = quad_history[-1]

    if (

        current is None

        or

        current == ""

    ):

        return previous_trade

    if previous_trade is None:

        return current

    if current == previous_trade:

        return previous_trade

    last_five = (

        quad_history[

            -settings.CONFIRM_DAYS:

        ]

    )

    last_fifteen = (

        quad_history[

            -settings.TRADE_LOOKBACK_DAYS:

        ]

    )

    five_day_streak = (

        len(

            last_five

        )

        ==

        settings.CONFIRM_DAYS

        and

        all(

            value == current

            for value in last_five

        )

    )

    occurrences = sum(

        value == current

        for value in last_fifteen

    )

    if (

        five_day_streak

        and

        occurrences

        >=

        settings.TRADE_THRESHOLD

    ):

        return current

    return previous_trade


def calculate_new_rows(

    historical_df: pd.DataFrame,

    new_rows: pd.DataFrame

) -> pd.DataFrame:

    """

    historical_df:
        Existing Excel history.

    new_rows:
        New FRED observations after
        the existing last date.

    Only new rows are returned.

    """

    combined = pd.concat(

        [

            historical_df,

            new_rows

        ],

        ignore_index=True

    )

    combined = (

        combined

        .sort_values(

            settings.DATE_COLUMN

        )

        .reset_index(

            drop=True

        )

    )

    combined[
        settings.VALUE_COLUMN
    ] = pd.to_numeric(

        combined[
            settings.VALUE_COLUMN
        ],

        errors="coerce"

    )

    # Existing values are preserved.
    #
    # New calculations are calculated
    # only for rows added after the
    # previous last date.

    last_existing_date = (

        historical_df[
            settings.DATE_COLUMN
        ]

        .max()

    )

    new_indices = (

        combined[
            settings.DATE_COLUMN
        ]

        >

        last_existing_date

    )

    # Historical calculation histories
    quad_history = []

    qad_history = []

    previous_3_day = None

    previous_confirmed = None

    previous_trade = None

    # Reconstruct historical state
    # from the existing workbook.
    for _, row in historical_df.iterrows():

        quad = row.get(

            settings.QUAD_COLUMN

        )

        qad = row.get(

            settings.QAD_VALUE_COLUMN

        )

        rule_3 = row.get(

            settings.RULE_3_COLUMN

        )

        confirmed = row.get(

            settings.CONFIRMED_COLUMN

        )

        trade = row.get(

            settings.TRADE_COLUMN

        )

        if pd.notna(quad):

            quad_history.append(

                str(
                    quad
                )

            )

        if pd.notna(qad):

            qad_history.append(

                int(
                    qad
                )

            )

        if pd.notna(rule_3):

            previous_3_day = str(

                rule_3

            )

        if pd.notna(confirmed):

            previous_confirmed = str(

                confirmed

            )

        if pd.notna(trade):

            previous_trade = str(

                trade

            )

    results = []

    for index, row in combined.iterrows():

        current_date = row[

            settings.DATE_COLUMN

        ]

        if (

            current_date
            <=
            last_existing_date

        ):

            continue

        current_value = float(

            row[
                settings.VALUE_COLUMN
            ]

        )

        # --------------------------------
        # 90-Day Slope
        # --------------------------------

        all_values_until_today = (

            combined

            .loc[

                :index,

                settings.VALUE_COLUMN

            ]

        )

        slope = calculate_90_day_slope(

            all_values_until_today

        )

        # --------------------------------
        # 90-Day Median
        # --------------------------------

        median_90 = calculate_90_day_median(

            all_values_until_today

        )

        # --------------------------------
        # 10-Year Median
        # --------------------------------

        median_10_year = calculate_10_year_median(

            all_values_until_today

        )

        # --------------------------------
        # QAD
        # --------------------------------

        quad = classify_quad(

            current_value,

            median_90,

            median_10_year

        )

        quad_history.append(

            quad

        )

        # --------------------------------
        # 3-Day Rule
        # --------------------------------

        rule_3 = calculate_3_day_rule(

            quad_history,

            previous_3_day

        )

        previous_3_day = rule_3

        # --------------------------------
        # QAD Value
        # --------------------------------

        qad = get_qad_value(

            quad

        )

        qad_history.append(

            qad

        )

        # --------------------------------
        # 7-Day Rule
        # --------------------------------

        rule_7 = calculate_7_day_rule(

            qad_history,

            None

        )

        # --------------------------------
        # Confirmed Regime
        # --------------------------------

        confirmed = calculate_confirmed_regime(

            quad_history,

            previous_confirmed

        )

        previous_confirmed = confirmed

        # --------------------------------
        # Trade Regime
        # --------------------------------

        trade = calculate_trade_regime(

            quad_history,

            previous_trade

        )

        previous_trade = trade

        results.append(

            {

                settings.DATE_COLUMN:
                current_date,

                settings.VALUE_COLUMN:
                current_value,

                settings.SLOPE_COLUMN:
                slope,

                settings.MEDIAN_90_COLUMN:
                median_90,

                settings.MEDIAN_10Y_COLUMN:
                median_10_year,

                settings.QUAD_COLUMN:
                quad,

                settings.RULE_3_COLUMN:
                rule_3,

                settings.QAD_VALUE_COLUMN:
                qad,

                settings.RULE_7_COLUMN:
                rule_7,

                settings.CONFIRMED_COLUMN:
                confirmed,

                settings.TRADE_COLUMN:
                trade

            }

        )

    return pd.DataFrame(

        results

    )