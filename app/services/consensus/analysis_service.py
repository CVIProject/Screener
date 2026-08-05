from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd

from app.services.consensus.models import (
    ConsensusConfig,
    ConsensusResult,
    WeeklyScreen,
)


def _min_max_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    valid = values.dropna()

    if valid.empty:
        return pd.Series(50.0, index=series.index)

    low = float(valid.min())
    high = float(valid.max())
    if math.isclose(low, high):
        score = pd.Series(100.0, index=series.index)
    else:
        score = (values - low) / (high - low) * 100.0

    if not higher_is_better:
        score = 100.0 - score

    return score.fillna(50.0).clip(0, 100)


def _longest_streak(values: Iterable[int]) -> int:
    weeks = sorted(set(int(value) for value in values))
    if not weeks:
        return 0

    longest = current = 1
    for previous, current_week in zip(weeks, weeks[1:]):
        if current_week == previous + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _rank_momentum(group: pd.DataFrame) -> tuple[float, str, float]:
    ranks = (
        group[["week_order", "weekly_rank"]]
        .dropna()
        .sort_values("week_order")
    )
    if len(ranks) < 2:
        return 50.0, "Insufficient History", 0.0

    x = ranks["week_order"].to_numpy(dtype=float)
    y = ranks["weekly_rank"].to_numpy(dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])

    score = float(np.clip(50.0 - slope * 15.0, 0.0, 100.0))
    if slope <= -0.15:
        label = "Improving"
    elif slope >= 0.15:
        label = "Weakening"
    else:
        label = "Stable"
    return score, label, slope


def _average_rank_score(average_rank: float, top_n: int) -> float:
    if pd.isna(average_rank):
        return 50.0
    denominator = max(top_n - 1, 1)
    return float(np.clip((1 - ((float(average_rank) - 1) / denominator)) * 100, 0, 100))


def _rank_stability_score(rank_std_dev: float, top_n: int) -> float:
    if pd.isna(rank_std_dev):
        return 50.0
    return float(np.clip(100 - (float(rank_std_dev) / max(top_n, 1) * 100), 0, 100))


def _recency_score(group: pd.DataFrame, total_weeks: int) -> float:
    denominator = sum(range(1, total_weeks + 1))
    if denominator == 0:
        return 0.0
    return float(np.clip(group["week_order"].sum() / denominator * 100, 0, 100))


def _recent_presence_score(group: pd.DataFrame, total_weeks: int, lookback: int) -> float:
    latest_orders = list(range(max(1, total_weeks - lookback + 1), total_weeks + 1))
    present = set(int(value) for value in group["week_order"])
    count = sum(1 for week in latest_orders if week in present)
    return count / max(len(latest_orders), 1) * 100.0



def _normalize_all_screening_rows(
    weekly_screens: list[WeeklyScreen],
) -> pd.DataFrame:
    """
    Normalize every filtered stock from every uploaded screening file.

    This dataset is used for portfolio analysis so a portfolio holding can be
    compared with its industry's top five even when the holding itself never
    appears in the weekly top five.
    """
    frames: list[pd.DataFrame] = []

    for screen in weekly_screens:
        df = screen.dataframe.copy()

        rank_source = df["industry_rank"].fillna(df["overall_rank"])
        missing_rank = rank_source.isna()

        if missing_rank.any():
            sort_columns: list[str] = []
            ascending: list[bool] = []

            for column, asc in (
                ("weighted_return", False),
                ("technical_score", False),
                ("trend_score", False),
                ("volatility_score", False),
                ("return_24m", False),
                ("return_6m", False),
            ):
                if df[column].notna().any():
                    sort_columns.append(column)
                    ascending.append(asc)

            if sort_columns:
                ordered = df.sort_values(
                    ["sector", "industry", *sort_columns],
                    ascending=[True, True, *ascending],
                    na_position="last",
                )
                calculated = (
                    ordered.groupby(["sector", "industry"], sort=False)
                    .cumcount()
                    .add(1)
                )
                calculated.index = ordered.index
                rank_source = rank_source.fillna(calculated.reindex(df.index))
            else:
                calculated = (
                    df.groupby(["sector", "industry"], sort=False)
                    .cumcount()
                    .add(1)
                )
                rank_source = rank_source.fillna(calculated)

        df["weekly_rank"] = pd.to_numeric(rank_source, errors="coerce")
        df["source_file"] = screen.filename
        df["week_label"] = screen.week_label
        df["week_order"] = screen.week_order
        df["week_date"] = (
            screen.week_date.isoformat() if screen.week_date else None
        )
        frames.append(df)

    all_rows = pd.concat(frames, ignore_index=True)

    return (
        all_rows.sort_values(
            ["week_order", "sector", "industry", "weekly_rank"],
            ascending=[True, True, True, True],
            na_position="last",
        )
        .drop_duplicates(["ticker", "week_order"], keep="first")
        .reset_index(drop=True)
    )


def _normalize_and_select_weekly_top_five(
    weekly_screens: list[WeeklyScreen],
    config: ConsensusConfig,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for screen in weekly_screens:
        df = screen.dataframe.copy()

        rank_source = (
            df["industry_rank"]
            .fillna(df["overall_rank"])
        )

        # When no rank exists, calculate within sector+industry from available scores.
        missing_rank = rank_source.isna()
        if missing_rank.any():
            sort_columns: list[str] = []
            ascending: list[bool] = []
            for column, asc in (
                ("weighted_return", False),
                ("technical_score", False),
                ("trend_score", False),
                ("volatility_score", False),
            ):
                if df[column].notna().any():
                    sort_columns.append(column)
                    ascending.append(asc)

            if sort_columns:
                calculated = (
                    df.sort_values(
                        ["sector", "industry", *sort_columns],
                        ascending=[True, True, *ascending],
                    )
                    .groupby(["sector", "industry"], sort=False)
                    .cumcount()
                    .add(1)
                )
                calculated = calculated.reindex(df.index)
                rank_source = rank_source.fillna(calculated)
            else:
                calculated = df.groupby(["sector", "industry"], sort=False).cumcount().add(1)
                rank_source = rank_source.fillna(calculated)

        df["weekly_rank"] = pd.to_numeric(rank_source, errors="coerce")

        # Only the weekly top five per sector+industry are compared.
        df = (
            df.sort_values(
                ["sector", "industry", "weekly_rank", "weighted_return"],
                ascending=[True, True, True, False],
                na_position="last",
            )
            .groupby(["sector", "industry"], group_keys=False)
            .head(config.top_n_per_industry)
            .copy()
        )

        df["source_file"] = screen.filename
        df["week_label"] = screen.week_label
        df["week_order"] = screen.week_order
        df["week_date"] = screen.week_date.isoformat() if screen.week_date else None
        frames.append(df)

    normalized = pd.concat(frames, ignore_index=True)
    normalized = (
        normalized.sort_values(
            ["week_order", "sector", "industry", "weekly_rank"],
            ascending=[True, True, True, True],
        )
        .drop_duplicates(["ticker", "week_order"], keep="first")
        .reset_index(drop=True)
    )
    return normalized


def _build_stock_summary(
    normalized: pd.DataFrame,
    total_weeks: int,
    config: ConsensusConfig,
) -> pd.DataFrame:
    rows: list[dict] = []

    for ticker, group in normalized.groupby("ticker", sort=False):
        group = group.sort_values("week_order")
        latest = group.iloc[-1]

        frequency = int(group["week_order"].nunique())
        longest_streak = _longest_streak(group["week_order"])
        momentum_score, momentum, rank_slope = _rank_momentum(group)
        average_rank = group["weekly_rank"].mean()
        rank_std_dev = group["weekly_rank"].std(ddof=0)

        rows.append(
            {
                "ticker": ticker,
                "company": latest["company"],
                "sector": latest["sector"],
                "industry": latest["industry"],
                "frequency": frequency,
                "total_weeks": total_weeks,
                "frequency_pct": frequency / total_weeks * 100,
                "longest_streak": longest_streak,
                "streak_pct": longest_streak / total_weeks * 100,
                "average_rank": average_rank,
                "median_rank": group["weekly_rank"].median(),
                "best_rank": group["weekly_rank"].min(),
                "worst_rank": group["weekly_rank"].max(),
                "rank_std_dev": rank_std_dev,
                "latest_rank": latest["weekly_rank"],
                "first_seen": group.iloc[0]["week_label"],
                "last_seen": latest["week_label"],
                "average_technical_score": group["technical_score"].mean(),
                "latest_technical_score": latest["technical_score"],
                "average_trend_score": group["trend_score"].mean(),
                "latest_trend_score": latest["trend_score"],
                "average_volatility_score": group["volatility_score"].mean(),
                "latest_volatility_score": latest["volatility_score"],
                "average_weighted_return": group["weighted_return"].mean(),
                "latest_weighted_return": latest["weighted_return"],
                "average_6m_return": group["return_6m"].mean(),
                "average_24m_return": group["return_24m"].mean(),
                "recency_score": _recency_score(group, total_weeks),
                "recent_presence_score": _recent_presence_score(
                    group, total_weeks, config.latest_weeks_required
                ),
                "momentum_score": momentum_score,
                "momentum": momentum,
                "rank_slope": rank_slope,
            }
        )

    summary = pd.DataFrame(rows)

    summary["frequency_score"] = summary["frequency_pct"]
    summary["average_rank_score"] = summary["average_rank"].map(
        lambda value: _average_rank_score(value, config.top_n_per_industry)
    )
    summary["rank_stability_score"] = summary["rank_std_dev"].map(
        lambda value: _rank_stability_score(value, config.top_n_per_industry)
    )
    summary["technical_component"] = _min_max_score(summary["average_technical_score"], True)
    summary["trend_component"] = _min_max_score(summary["average_trend_score"], True)
    summary["volatility_component"] = _min_max_score(
        summary["average_volatility_score"],
        config.higher_volatility_score_is_better,
    )
    summary["streak_score"] = summary["streak_pct"]

    # Blend recency with explicit presence in the latest configured weeks.
    summary["effective_recency_score"] = (
        summary["recency_score"] * 0.60
        + summary["recent_presence_score"] * 0.40
    )

    summary["consensus_score"] = (
        summary["frequency_score"] * config.frequency_weight
        + summary["average_rank_score"] * config.average_rank_weight
        + summary["rank_stability_score"] * config.rank_stability_weight
        + summary["effective_recency_score"] * config.recency_weight
        + summary["momentum_score"] * config.momentum_weight
        + summary["technical_component"] * config.technical_weight
        + summary["trend_component"] * config.trend_weight
        + summary["volatility_component"] * config.volatility_weight
        + summary["streak_score"] * config.streak_weight
    ).round(2)

    required_frequency = min(config.minimum_frequency, total_weeks)

    def recommendation(row: pd.Series) -> str:
        if (
            row["consensus_score"] >= config.high_conviction_score
            and row["frequency"] >= required_frequency
            and row["recent_presence_score"] > 0
        ):
            return "High Conviction"
        if (
            row["consensus_score"] >= config.strong_candidate_score
            and row["frequency"] >= max(2, required_frequency - 1)
            and row["recent_presence_score"] > 0
        ):
            return "Strong Candidate"
        if row["consensus_score"] >= 55:
            return "Watch"
        return "Low Conviction"

    summary["recommendation"] = summary.apply(recommendation, axis=1)
    summary["appears_every_week"] = summary["frequency"].eq(total_weeks)

    summary = summary.sort_values(
        [
            "sector", "industry", "consensus_score", "frequency",
            "longest_streak", "average_rank", "rank_std_dev", "latest_rank",
        ],
        ascending=[True, True, False, False, False, True, True, True],
    ).reset_index(drop=True)

    summary["industry_consensus_rank"] = (
        summary.groupby(["sector", "industry"]).cumcount() + 1
    )
    summary["overall_consensus_rank"] = (
        summary["consensus_score"].rank(method="first", ascending=False).astype(int)
    )
    return summary


def _build_consensus_top_five(
    summary: pd.DataFrame,
    config: ConsensusConfig,
) -> pd.DataFrame:
    return (
        summary[summary["industry_consensus_rank"] <= config.top_n_per_industry]
        .sort_values(
            ["sector", "industry", "industry_consensus_rank"],
            ascending=[True, True, True],
        )
        .reset_index(drop=True)
    )


def _build_next_week_candidates(
    consensus_top_five: pd.DataFrame,
    total_weeks: int,
    config: ConsensusConfig,
) -> pd.DataFrame:
    required_frequency = min(config.minimum_frequency, total_weeks)

    eligible = consensus_top_five[
        (consensus_top_five["frequency"] >= required_frequency)
        & (consensus_top_five["recent_presence_score"] > 0)
        & consensus_top_five["momentum"].isin(["Improving", "Stable", "Insufficient History"])
    ].copy()

    if eligible.empty:
        eligible = consensus_top_five[
            consensus_top_five["recent_presence_score"] > 0
        ].copy()

    eligible["next_week_rank"] = (
        eligible.groupby(["sector", "industry"])["consensus_score"]
        .rank(method="first", ascending=False)
    )

    return (
        eligible[eligible["next_week_rank"] <= config.top_n_per_industry]
        .sort_values(["sector", "industry", "next_week_rank"])
        .reset_index(drop=True)
    )



def _build_portfolio_outputs(
    portfolio: pd.DataFrame | None,
    all_stock_summary: pd.DataFrame,
    consensus_top_five: pd.DataFrame,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    Compare every portfolio holding with the final top five stocks in the same
    industry.

    The holding does not need to be present in the final top five. Its score is
    calculated from all uploaded screening rows, then ranked against the five
    final industry candidates.
    """
    if portfolio is None or portfolio.empty:
        return None, None

    comparison = portfolio.merge(
        all_stock_summary,
        on="ticker",
        how="left",
        suffixes=("_portfolio", ""),
    )

    top_five_groups: dict[tuple[str, str], pd.DataFrame] = {
        (str(sector), str(industry)): group.sort_values(
            "industry_consensus_rank"
        ).copy()
        for (sector, industry), group in consensus_top_five.groupby(
            ["sector", "industry"],
            sort=False,
        )
    }

    output_rows: list[dict] = []
    replacement_rows: list[dict] = []

    for _, holding in comparison.iterrows():
        ticker = str(holding["ticker"]).strip().upper()
        portfolio_name = holding.get("portfolio_name")

        sector = holding.get("sector")
        industry = holding.get("industry")

        if pd.isna(sector) or not str(sector).strip():
            sector = holding.get("sector_portfolio")
        if pd.isna(industry) or not str(industry).strip():
            industry = holding.get("industry_portfolio")

        has_screening_data = (
            pd.notna(holding.get("consensus_score"))
            and pd.notna(sector)
            and pd.notna(industry)
        )

        base = holding.to_dict()
        base["portfolio_name"] = portfolio_name
        base["ticker"] = ticker
        base["sector"] = sector
        base["industry"] = industry

        if not has_screening_data:
            base.update(
                {
                    "portfolio_industry_rank": pd.NA,
                    "portfolio_status": "No Screening Match",
                    "portfolio_action": "REVIEW - NO SCREENING DATA",
                    "best_industry_ticker": pd.NA,
                    "best_industry_company": pd.NA,
                    "best_industry_score": pd.NA,
                    "score_gap_to_best": pd.NA,
                    "is_final_top_five": False,
                }
            )
            output_rows.append(base)
            continue

        key = (str(sector), str(industry))
        industry_top = top_five_groups.get(key, pd.DataFrame())

        if industry_top.empty:
            base.update(
                {
                    "portfolio_industry_rank": pd.NA,
                    "portfolio_status": "Industry Top Five Missing",
                    "portfolio_action": "REVIEW",
                    "best_industry_ticker": pd.NA,
                    "best_industry_company": pd.NA,
                    "best_industry_score": pd.NA,
                    "score_gap_to_best": pd.NA,
                    "is_final_top_five": False,
                }
            )
            output_rows.append(base)
            continue

        holding_score = float(holding["consensus_score"])
        comparison_scores = [
            (str(row["ticker"]), float(row["consensus_score"]))
            for _, row in industry_top.iterrows()
            if str(row["ticker"]).strip().upper() != ticker
        ]
        comparison_scores.append((ticker, holding_score))
        comparison_scores.sort(key=lambda item: (-item[1], item[0]))

        portfolio_rank = next(
            index
            for index, (candidate_ticker, _) in enumerate(
                comparison_scores,
                start=1,
            )
            if candidate_ticker == ticker
        )

        best = industry_top.sort_values(
            [
                "consensus_score",
                "frequency",
                "longest_streak",
                "average_rank",
            ],
            ascending=[False, False, False, True],
        ).iloc[0]

        top_five_tickers = set(
            industry_top["ticker"].astype(str).str.strip().str.upper()
        )
        is_top_five = ticker in top_five_tickers
        score_gap = round(
            float(best["consensus_score"]) - holding_score,
            2,
        )

        if portfolio_rank <= 2:
            status = "Leading Industry Holding"
            action = "HOLD / ADD"
        elif is_top_five or portfolio_rank <= 5:
            status = "Competitive Industry Holding"
            action = "HOLD"
        else:
            status = "Below Industry Top Five"
            action = f"REPLACE WITH {best['ticker']}"

        base.update(
            {
                "portfolio_industry_rank": portfolio_rank,
                "portfolio_status": status,
                "portfolio_action": action,
                "best_industry_ticker": best["ticker"],
                "best_industry_company": best["company"],
                "best_industry_score": best["consensus_score"],
                "score_gap_to_best": score_gap,
                "is_final_top_five": is_top_five,
            }
        )
        output_rows.append(base)

        if action.startswith("REPLACE WITH"):
            replacement_rows.append(
                {
                    "portfolio_name": portfolio_name,
                    "portfolio_ticker": ticker,
                    "portfolio_company": (
                        holding.get("company_portfolio")
                        if pd.notna(holding.get("company_portfolio"))
                        else ticker
                    ),
                    "sector": sector,
                    "industry": industry,
                    "portfolio_industry_rank": portfolio_rank,
                    "portfolio_score": holding_score,
                    "suggested_ticker": best["ticker"],
                    "suggested_company": best["company"],
                    "suggested_score": best["consensus_score"],
                    "score_improvement": score_gap,
                    "action": action,
                }
            )

    portfolio_comparison = pd.DataFrame(output_rows)

    if not portfolio_comparison.empty:
        portfolio_comparison = portfolio_comparison.sort_values(
            [
                "sector",
                "industry",
                "portfolio_industry_rank",
                "portfolio_name",
                "ticker",
            ],
            ascending=[True, True, True, True, True],
            na_position="last",
        ).reset_index(drop=True)

    return portfolio_comparison, pd.DataFrame(replacement_rows)

def analyze_consensus(
    weekly_screens: list[WeeklyScreen],
    portfolio: pd.DataFrame | None,
    config: ConsensusConfig,
) -> ConsensusResult:
    config.validate()

    all_rows = _normalize_all_screening_rows(weekly_screens)
    normalized = _normalize_and_select_weekly_top_five(weekly_screens, config)
    total_weeks = len(weekly_screens)

    # Final top five is based only on weekly top-five appearances.
    summary = _build_stock_summary(normalized, total_weeks, config)
    consensus_top_five = _build_consensus_top_five(summary, config)
    next_week = _build_next_week_candidates(
        consensus_top_five,
        total_weeks,
        config,
    )

    # Portfolio holdings are scored using all filtered stocks, not only top five.
    all_stock_summary = _build_stock_summary(
        all_rows,
        total_weeks,
        config,
    )
    portfolio_comparison, replacements = _build_portfolio_outputs(
        portfolio,
        all_stock_summary,
        consensus_top_five,
    )

    required_frequency = min(config.minimum_frequency, total_weeks)
    dashboard = {
        "uploaded_files": total_weeks,
        "date_range": (
            f"{weekly_screens[0].week_label} to {weekly_screens[-1].week_label}"
            if weekly_screens else ""
        ),
        "unique_top_five_stocks": int(summary["ticker"].nunique()),
        "common_stocks": int((summary["frequency"] >= required_frequency).sum()),
        "every_week_stocks": int(summary["appears_every_week"].sum()),
        "high_conviction_stocks": int(
            summary["recommendation"].eq("High Conviction").sum()
        ),
        "strong_candidates": int(
            summary["recommendation"].eq("Strong Candidate").sum()
        ),
        "portfolio_stocks": int(len(portfolio)) if portfolio is not None else 0,
        "portfolio_consensus_matches": int(
            portfolio_comparison["portfolio_action"]
            .isin(["HOLD / ADD", "HOLD"])
            .sum()
        ) if portfolio_comparison is not None else 0,
        "replacement_reviews": int(len(replacements))
        if replacements is not None else 0,
    }

    return ConsensusResult(
        weekly_screens=weekly_screens,
        normalized_rows=normalized,
        stock_summary=summary,
        weekly_top_five=normalized,
        consensus_top_five=consensus_top_five,
        next_week_candidates=next_week,
        portfolio_comparison=portfolio_comparison,
        replacement_suggestions=replacements,
        dashboard_metrics=dashboard,
    )
