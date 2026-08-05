from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "ticker": ("ticker", "symbol", "sym", "stock symbol", "stock", "security symbol"),
    "company": ("company", "company name", "name", "stock name", "security name"),
    "sector": ("sector", "gics sector", "s&p sector", "sp sector", "sector name"),
    "industry": (
        "industry", "industry group", "industry_group", "gics industry",
        "industry name", "ibd industry group"
    ),
    "overall_rank": ("overall rank", "final rank", "rank", "stock rank", "overall_rank"),
    "sector_rank": ("sector rank", "sector_rank"),
    "industry_rank": ("industry rank", "industry_rank", "industry group rank"),
    "technical_score": ("technical score", "technical", "tech score", "technical_score"),
    "trend_score": ("trend score", "trend", "trend_score"),
    "volatility_score": ("volatility score", "volatility", "vol score", "volatility_score"),
    "weighted_return": ("weighted return", "weighted_return", "return score", "weighted score"),
    "return_6m": (
        "6m return", "6 month return", "six month return", "return 6m",
        "6-month return", "6 months return"
    ),
    "return_24m": (
        "24m return", "24 month return", "twenty four month return",
        "return 24m", "24-month return", "24 months return"
    ),
}


def safe_text(value: object) -> str:
    """
    Convert spreadsheet values to text without evaluating pd.NA as boolean.

    `value or ""` must not be used because bool(pd.NA) raises:
    TypeError: boolean value of NA is ambiguous.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def normalize_header(value: object) -> str:
    text = safe_text(value).strip().lower()
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9%&/ ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_company_name(value: object) -> str:
    text = safe_text(value).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)

    # Remove only a trailing dividend-like number.
    text = re.sub(r"\s+\d+(?:\.\d+)?%?\s*$", "", text)
    return text.strip()


def normalize_ticker(value: object) -> str:
    text = safe_text(value).replace("\u00a0", "").strip().upper()
    text = re.sub(r"\s+", "", text)

    invalid = {
        "", "NAN", "NONE", "<NA>", "NA", "N/A",
        "SYMBOL", "TICKER", "STOCK", "CASH", "$CASH",
    }
    return "" if text in invalid else text


def build_column_mapping(columns: Iterable[object]) -> dict[str, str]:
    normalized = {normalize_header(column): str(column) for column in columns}
    mapping: dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            match = normalized.get(normalize_header(alias))
            if match:
                mapping[canonical] = match
                break
    return mapping


def standardize_screening_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(f"{source_name}: the sheet is empty.")

    df = df.copy()
    df.columns = [safe_text(column).strip() for column in df.columns]
    mapping = build_column_mapping(df.columns)

    required = ["ticker", "sector", "industry"]
    missing = [column for column in required if column not in mapping]
    if missing:
        raise ValueError(
            f"{source_name}: missing required columns {missing}. "
            f"Available columns are {list(df.columns)}"
        )

    df = df.rename(columns={original: canonical for canonical, original in mapping.items()})

    optional = [
        "company", "overall_rank", "sector_rank", "industry_rank",
        "technical_score", "trend_score", "volatility_score",
        "weighted_return", "return_6m", "return_24m",
    ]
    for column in optional:
        if column not in df.columns:
            df[column] = pd.NA

    columns = [
        "ticker", "company", "sector", "industry",
        "overall_rank", "sector_rank", "industry_rank",
        "technical_score", "trend_score", "volatility_score",
        "weighted_return", "return_6m", "return_24m",
    ]
    df = df[columns].copy()

    df["ticker"] = df["ticker"].map(normalize_ticker)
    df["company"] = df["company"].map(clean_company_name)
    df.loc[df["company"].eq(""), "company"] = df["ticker"]

    df["sector"] = (
        df["sector"].fillna("Unknown").astype(str)
        .str.replace("\u00a0", " ", regex=False).str.strip()
    )
    df["industry"] = (
        df["industry"].fillna("Unknown").astype(str)
        .str.replace("\u00a0", " ", regex=False).str.strip()
    )

    df = df[df["ticker"].ne("")].copy()

    numeric_columns = [
        "overall_rank", "sector_rank", "industry_rank",
        "technical_score", "trend_score", "volatility_score",
        "weighted_return", "return_6m", "return_24m",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column].astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", "", regex=False),
            errors="coerce",
        )

    rank_priority = (
        df["industry_rank"]
        .fillna(df["overall_rank"])
        .fillna(float("inf"))
    )
    df["_rank_priority"] = rank_priority
    df["_score_priority"] = df["weighted_return"].fillna(float("-inf"))

    return (
        df.sort_values(
            ["ticker", "_rank_priority", "_score_priority"],
            ascending=[True, True, False],
        )
        .drop_duplicates("ticker", keep="first")
        .drop(columns=["_rank_priority", "_score_priority"])
        .reset_index(drop=True)
    )


def standardize_portfolio_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Standard row-based portfolio format.

    Example:
    Ticker | Company | Portfolio Name | Shares | ...
    """
    if df is None or df.empty:
        raise ValueError(f"{source_name}: the portfolio sheet is empty.")

    normalized = {normalize_header(column): str(column) for column in df.columns}

    ticker_column = next(
        (
            normalized[key]
            for key in ("ticker", "symbol", "sym", "stock", "stock symbol")
            if key in normalized
        ),
        None,
    )
    if ticker_column is None:
        raise ValueError(
            f"{source_name}: no row-based ticker column was detected."
        )

    result = pd.DataFrame(index=df.index)
    result["ticker"] = df[ticker_column].map(normalize_ticker)

    aliases = {
        "company": ("company", "company name", "name"),
        "portfolio_name": ("portfolio name", "portfolio", "account", "strategy", "model"),
        "shares": ("shares", "quantity", "qty"),
        "cost_basis": ("cost basis", "average cost", "avg cost", "cost"),
        "market_value": ("market value", "current value", "value"),
        "sector": ("sector",),
        "industry": ("industry", "industry group"),
    }

    for target, choices in aliases.items():
        source = next((normalized[c] for c in choices if c in normalized), None)
        if source is None:
            result[target] = pd.Series(pd.NA, index=df.index, dtype="object")
        else:
            result[target] = df[source].values

    result["company"] = result["company"].map(clean_company_name)
    for column in ("shares", "cost_basis", "market_value"):
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result[result["ticker"].ne("")].copy()
    return result.drop_duplicates(
        ["ticker", "portfolio_name"], keep="first"
    ).reset_index(drop=True)


def parse_portfolio_model_matrix(
    raw: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    """
    Parse model workbooks like:

        Models | Sanctuary | Hope | Goliath | Faith
               | Symbol    | Symbol | Symbol | Symbol
               | CASH      | CASH   | $CASH  | CASH
               | AHR       | ANET   | NEE    | AHR
               | ...

    Portfolio/model names are column headers and ticker symbols run vertically.
    """
    if raw is None or raw.empty:
        raise ValueError(f"{source_name}: the portfolio sheet is empty.")

    raw = raw.copy().dropna(axis=0, how="all").dropna(axis=1, how="all")
    if raw.empty or raw.shape[1] < 2:
        raise ValueError(f"{source_name}: no portfolio model matrix was detected.")

    # Detect a row containing two or more 'Symbol' labels.
    symbol_row_index = None
    for index, row in raw.iterrows():
        normalized_values = [normalize_header(value) for value in row.tolist()]
        symbol_count = sum(value in {"symbol", "ticker", "stock symbol"} for value in normalized_values)
        if symbol_count >= 2:
            symbol_row_index = index
            break

    records: list[dict[str, object]] = []

    if symbol_row_index is not None:
        position = raw.index.get_loc(symbol_row_index)
        if position == 0:
            raise ValueError(
                f"{source_name}: symbol row exists but portfolio names were not found above it."
            )

        portfolio_header_row = raw.iloc[position - 1]
        data = raw.iloc[position + 1:]

        for column_position in range(raw.shape[1]):
            portfolio_name = safe_text(portfolio_header_row.iloc[column_position]).strip()
            symbol_marker = normalize_header(raw.loc[symbol_row_index].iloc[column_position])

            if symbol_marker not in {"symbol", "ticker", "stock symbol"}:
                continue
            if not portfolio_name or normalize_header(portfolio_name) in {"models", "model"}:
                continue

            for value in data.iloc[:, column_position]:
                ticker = normalize_ticker(value)
                if not ticker:
                    continue
                records.append(
                    {
                        "ticker": ticker,
                        "company": ticker,
                        "portfolio_name": portfolio_name,
                        "shares": pd.NA,
                        "cost_basis": pd.NA,
                        "market_value": pd.NA,
                        "sector": pd.NA,
                        "industry": pd.NA,
                    }
                )

    # Fallback for pandas default-header read:
    # columns are Models, Sanctuary, Hope, Goliath, Faith and row 0 contains Symbol.
    if not records:
        header_values = [safe_text(value).strip() for value in raw.iloc[0].tolist()]
        for column_position in range(1, raw.shape[1]):
            portfolio_name = safe_text(raw.iloc[0, column_position]).strip()
            if not portfolio_name:
                continue

            for value in raw.iloc[1:, column_position]:
                ticker = normalize_ticker(value)
                if not ticker:
                    continue
                records.append(
                    {
                        "ticker": ticker,
                        "company": ticker,
                        "portfolio_name": portfolio_name,
                        "shares": pd.NA,
                        "cost_basis": pd.NA,
                        "market_value": pd.NA,
                        "sector": pd.NA,
                        "industry": pd.NA,
                    }
                )

    if not records:
        raise ValueError(
            f"{source_name}: neither a row-based portfolio nor a model matrix was detected."
        )

    result = pd.DataFrame(records)
    return result.drop_duplicates(
        ["ticker", "portfolio_name"], keep="first"
    ).reset_index(drop=True)
