from __future__ import annotations

from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings


OUTPUT_COLUMNS = [
    settings.DATE_COLUMN,
    settings.VALUE_COLUMN,
    settings.SLOPE_COLUMN,
    settings.MEDIAN_90_COLUMN,
    settings.MEDIAN_10Y_COLUMN,
    settings.QUAD_COLUMN,
    settings.RULE_3_COLUMN,
    settings.QAD_VALUE_COLUMN,
    settings.RULE_7_COLUMN,
    settings.CONFIRMED_COLUMN,
    settings.TRADE_COLUMN,
]


QUAD_TO_VALUE = {
    "Recovery  QAD 1": 1,
    "Growth QAD 2": 2,
    "Overheating QAD 3": 3,
    "recession QAD 4": 4,
}


def clean_optional_string(
    value: object,
) -> Optional[str]:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    return text or None


def clean_optional_integer(
    value: object,
) -> Optional[int]:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def calculate_excel_slope(
    values: pd.Series,
) -> float:
    """
    Calculate a linear regression slope equivalent to Excel SLOPE.

    Known x-values:
        1, 2, 3, ..., N

    Known y-values:
        BAMLH0A0HYM2 observations
    """
    numeric_values = (
        pd.to_numeric(
            values,
            errors="coerce",
        )
        .dropna()
        .astype(float)
    )

    if len(numeric_values) < 2:
        return float("nan")

    x_values = np.arange(
        1,
        len(numeric_values) + 1,
        dtype=float,
    )

    y_values = numeric_values.to_numpy(
        dtype=float
    )

    slope = np.polyfit(
        x_values,
        y_values,
        1,
    )[0]

    return round(
        float(slope),
        3,
    )


def calculate_rolling_slope(
    all_values: pd.Series,
) -> float:
    """
    Calculate the slope using the configured number of observations.
    """
    window = all_values.tail(
        settings.SLOPE_WINDOW
    )

    return calculate_excel_slope(
        window
    )


def calculate_rolling_median(
    all_values: pd.Series,
    window_size: int,
) -> float:
    """
    Calculate the median from the latest window_size observations.
    """
    window = (
        pd.to_numeric(
            all_values,
            errors="coerce",
        )
        .dropna()
        .tail(window_size)
    )

    if window.empty:
        return float("nan")

    return round(
        float(window.median()),
        2,
    )


def classify_quad(
    current_value: float,
    median_90: float,
    median_10_year: float,
) -> str:
    """
    Classify the current observation into one of four quadrants.
    """
    if (
        current_value > median_90
        and current_value > median_10_year
    ):
        return "recession QAD 4"

    if (
        current_value > median_90
        and current_value < median_10_year
    ):
        return "Recovery  QAD 1"

    if (
        current_value < median_90
        and current_value > median_10_year
    ):
        return "Overheating QAD 3"

    return "Growth QAD 2"


def get_qad_value(
    quad: str,
) -> int:
    try:
        return QUAD_TO_VALUE[quad]
    except KeyError as exc:
        raise ValueError(
            f"Unknown quadrant value: {quad}"
        ) from exc


def calculate_3_day_rule(
    quad_history: list[str],
    previous_rule: Optional[str],
) -> str:
    """
    Change the confirmed 3-day rule only when the latest three
    quadrant values are identical.
    """
    current_quad = quad_history[-1]

    if len(quad_history) < 3:
        return previous_rule or current_quad

    last_three = quad_history[-3:]

    if (
        last_three[0]
        == last_three[1]
        == last_three[2]
    ):
        return current_quad

    return previous_rule or current_quad


def calculate_mode_with_recent_tie_break(
    values: list[int],
) -> Optional[int]:
    """
    Return the most frequent value.

    When multiple values have the same frequency, return the most
    recently occurring tied value.
    """
    if not values:
        return None

    counts = Counter(values)
    maximum_count = max(counts.values())

    tied_values = {
        value
        for value, count in counts.items()
        if count == maximum_count
    }

    for value in reversed(values):
        if value in tied_values:
            return value

    return values[-1]


def calculate_7_day_rule(
    qad_history: list[int],
) -> Optional[int]:
    """
    Return the mode of the latest seven QAD values.
    """
    if not qad_history:
        return None

    if len(qad_history) < 7:
        return qad_history[-1]

    return calculate_mode_with_recent_tie_break(
        qad_history[-7:]
    )


def calculate_confirmed_regime(
    quad_history: list[str],
    previous_confirmed: Optional[str],
) -> str:
    """
    Change the confirmed regime only after the current quadrant has
    appeared for five consecutive observations.
    """
    current_quad = quad_history[-1]

    if previous_confirmed is None:
        return current_quad

    if current_quad == previous_confirmed:
        return previous_confirmed

    if len(quad_history) < settings.CONFIRM_DAYS:
        return previous_confirmed

    recent_values = quad_history[
        -settings.CONFIRM_DAYS:
    ]

    has_required_streak = all(
        value == current_quad
        for value in recent_values
    )

    if has_required_streak:
        return current_quad

    return previous_confirmed


def calculate_trade_regime(
    quad_history: list[str],
    previous_trade: Optional[str],
) -> str:
    """
    Change the trade regime when:

    1. The current quadrant appears for five consecutive observations.
    2. The same quadrant appears at least nine times in the latest
       fifteen observations.
    """
    current_quad = quad_history[-1]

    if previous_trade is None:
        return current_quad

    if current_quad == previous_trade:
        return previous_trade

    last_five = quad_history[
        -settings.CONFIRM_DAYS:
    ]

    last_fifteen = quad_history[
        -settings.TRADE_LOOKBACK_DAYS:
    ]

    has_five_day_streak = (
        len(last_five)
        == settings.CONFIRM_DAYS
        and all(
            value == current_quad
            for value in last_five
        )
    )

    occurrence_count = sum(
        value == current_quad
        for value in last_fifteen
    )

    if (
        has_five_day_streak
        and occurrence_count
        >= settings.TRADE_THRESHOLD
    ):
        return current_quad

    return previous_trade


def prepare_historical_dataframe(
    historical_df: pd.DataFrame,
) -> pd.DataFrame:
    missing_columns = [
        column
        for column in OUTPUT_COLUMNS
        if column not in historical_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "The historical workbook is missing columns: "
            + ", ".join(missing_columns)
        )

    result = historical_df[
        OUTPUT_COLUMNS
    ].copy()

    result[settings.DATE_COLUMN] = pd.to_datetime(
        result[settings.DATE_COLUMN],
        errors="coerce",
    )

    result[settings.VALUE_COLUMN] = pd.to_numeric(
        result[settings.VALUE_COLUMN],
        errors="coerce",
    )

    result = result.dropna(
        subset=[
            settings.DATE_COLUMN,
            settings.VALUE_COLUMN,
        ]
    )

    result = (
        result
        .sort_values(settings.DATE_COLUMN)
        .drop_duplicates(
            subset=[settings.DATE_COLUMN],
            keep="last",
        )
        .reset_index(drop=True)
    )

    if result.empty:
        raise ValueError(
            "The historical workbook contains no valid observations."
        )

    return result


def prepare_new_values_dataframe(
    new_values_df: pd.DataFrame,
) -> pd.DataFrame:
    required_columns = [
        settings.DATE_COLUMN,
        settings.VALUE_COLUMN,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in new_values_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "The new-values workbook is missing columns: "
            + ", ".join(missing_columns)
        )

    result = new_values_df[
        required_columns
    ].copy()

    result[settings.DATE_COLUMN] = pd.to_datetime(
        result[settings.DATE_COLUMN],
        errors="coerce",
    )

    result[settings.VALUE_COLUMN] = pd.to_numeric(
        result[settings.VALUE_COLUMN],
        errors="coerce",
    )

    invalid_mask = (
        result[settings.DATE_COLUMN].isna()
        | result[settings.VALUE_COLUMN].isna()
    )

    if invalid_mask.any():
        invalid_rows = result.index[
            invalid_mask
        ].tolist()

        raise ValueError(
            "The new-values workbook contains invalid data at "
            f"rows: {', '.join(str(row + 2) for row in invalid_rows)}"
        )

    if (
        result[settings.VALUE_COLUMN] < 0
    ).any():
        raise ValueError(
            "BAMLH0A0HYM2 values cannot be negative."
        )

    result = (
        result
        .sort_values(settings.DATE_COLUMN)
        .drop_duplicates(
            subset=[settings.DATE_COLUMN],
            keep="last",
        )
        .reset_index(drop=True)
    )

    if result.empty:
        raise ValueError(
            "The new-values workbook contains no valid observations."
        )

    return result


def get_historical_state(
    historical_df: pd.DataFrame,
) -> tuple[
    list[str],
    list[int],
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Build the existing state required to calculate newly appended rows.
    """
    quad_history: list[str] = []
    qad_history: list[int] = []

    previous_rule_3: Optional[str] = None
    previous_confirmed: Optional[str] = None
    previous_trade: Optional[str] = None

    for _, row in historical_df.iterrows():
        quad = clean_optional_string(
            row.get(settings.QUAD_COLUMN)
        )

        qad_value = clean_optional_integer(
            row.get(settings.QAD_VALUE_COLUMN)
        )

        rule_3 = clean_optional_string(
            row.get(settings.RULE_3_COLUMN)
        )

        confirmed = clean_optional_string(
            row.get(settings.CONFIRMED_COLUMN)
        )

        trade = clean_optional_string(
            row.get(settings.TRADE_COLUMN)
        )

        if quad is not None:
            quad_history.append(quad)

        if qad_value is not None:
            qad_history.append(qad_value)

        if rule_3 is not None:
            previous_rule_3 = rule_3

        if confirmed is not None:
            previous_confirmed = confirmed

        if trade is not None:
            previous_trade = trade

    if not quad_history:
        raise ValueError(
            "The historical workbook contains no valid quadrant history."
        )

    if not qad_history:
        raise ValueError(
            "The historical workbook contains no valid QAD Value history."
        )

    return (
        quad_history,
        qad_history,
        previous_rule_3,
        previous_confirmed,
        previous_trade,
    )


def append_new_observations(
    historical_df: pd.DataFrame,
    new_values_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Append every new observation sequentially.

    Each new row is calculated using:
    - All historical rows.
    - All new rows already calculated during this request.
    """
    historical = prepare_historical_dataframe(
        historical_df
    )

    new_values = prepare_new_values_dataframe(
        new_values_df
    )

    latest_historical_date = historical[
        settings.DATE_COLUMN
    ].max()

    historical_dates = set(
        historical[
            settings.DATE_COLUMN
        ].dt.normalize()
    )

    pending = new_values[
        (
            new_values[settings.DATE_COLUMN]
            > latest_historical_date
        )
        &
        (
            ~new_values[
                settings.DATE_COLUMN
            ]
            .dt.normalize()
            .isin(historical_dates)
        )
    ].copy()

    pending = (
        pending
        .sort_values(settings.DATE_COLUMN)
        .reset_index(drop=True)
    )

    if pending.empty:
        raise ValueError(
            "No new rows were found. All new-values dates already "
            "exist in the historical workbook or are not later than "
            f"the latest historical date "
            f"{latest_historical_date.date()}."
        )

    (
        quad_history,
        qad_history,
        previous_rule_3,
        previous_confirmed,
        previous_trade,
    ) = get_historical_state(
        historical
    )

    result = historical[
        OUTPUT_COLUMNS
    ].copy()

    appended_rows: list[
        dict[str, object]
    ] = []

    for _, new_input_row in pending.iterrows():
        new_date = pd.Timestamp(
            new_input_row[
                settings.DATE_COLUMN
            ]
        )

        new_value = float(
            new_input_row[
                settings.VALUE_COLUMN
            ]
        )

        # Include the current new value when calculating
        # slope and medians.
        all_values = pd.concat(
            [
                result[
                    settings.VALUE_COLUMN
                ],
                pd.Series(
                    [new_value],
                    dtype=float,
                ),
            ],
            ignore_index=True,
        )

        slope = calculate_rolling_slope(
            all_values
        )

        median_90 = calculate_rolling_median(
            all_values,
            settings.MEDIAN_90_WINDOW,
        )

        median_10_year = calculate_rolling_median(
            all_values,
            settings.MEDIAN_10Y_WINDOW,
        )

        quad = classify_quad(
            current_value=new_value,
            median_90=median_90,
            median_10_year=median_10_year,
        )

        quad_history.append(
            quad
        )

        rule_3 = calculate_3_day_rule(
            quad_history=quad_history,
            previous_rule=previous_rule_3,
        )

        qad_value = get_qad_value(
            quad
        )

        qad_history.append(
            qad_value
        )

        rule_7 = calculate_7_day_rule(
            qad_history
        )

        confirmed_regime = (
            calculate_confirmed_regime(
                quad_history=quad_history,
                previous_confirmed=previous_confirmed,
            )
        )

        trade_regime = calculate_trade_regime(
            quad_history=quad_history,
            previous_trade=previous_trade,
        )

        calculated_row: dict[str, object] = {
            settings.DATE_COLUMN:
                new_date,

            settings.VALUE_COLUMN:
                new_value,

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
                qad_value,

            settings.RULE_7_COLUMN:
                rule_7,

            settings.CONFIRMED_COLUMN:
                confirmed_regime,

            settings.TRADE_COLUMN:
                trade_regime,
        }

        appended_rows.append(
            calculated_row
        )

        result = pd.concat(
            [
                result,
                pd.DataFrame(
                    [calculated_row],
                    columns=OUTPUT_COLUMNS,
                ),
            ],
            ignore_index=True,
        )

        # Carry the newly calculated state into the next row.
        previous_rule_3 = rule_3
        previous_confirmed = confirmed_regime
        previous_trade = trade_regime

    result = (
        result
        .sort_values(settings.DATE_COLUMN)
        .drop_duplicates(
            subset=[settings.DATE_COLUMN],
            keep="last",
        )
        .reset_index(drop=True)
    )

    appended_dataframe = pd.DataFrame(
        appended_rows,
        columns=OUTPUT_COLUMNS,
    )

    return result, appended_dataframe