from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ConsensusConfig:
    top_n_per_industry: int = 5
    minimum_frequency: int = 4
    high_conviction_score: float = 80.0
    strong_candidate_score: float = 68.0
    latest_weeks_required: int = 2

    frequency_weight: float = 0.25
    average_rank_weight: float = 0.15
    rank_stability_weight: float = 0.10
    recency_weight: float = 0.15
    momentum_weight: float = 0.10
    technical_weight: float = 0.10
    trend_weight: float = 0.05
    volatility_weight: float = 0.05
    streak_weight: float = 0.05

    # Set False when the input is raw volatility where lower is better.
    higher_volatility_score_is_better: bool = True

    def validate(self) -> None:
        total = (
            self.frequency_weight
            + self.average_rank_weight
            + self.rank_stability_weight
            + self.recency_weight
            + self.momentum_weight
            + self.technical_weight
            + self.trend_weight
            + self.volatility_weight
            + self.streak_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Consensus weights must total 1.0; current total is {total:.6f}.")
        if self.top_n_per_industry < 1:
            raise ValueError("top_n_per_industry must be at least 1.")
        if self.minimum_frequency < 1:
            raise ValueError("minimum_frequency must be at least 1.")
        if self.latest_weeks_required < 1:
            raise ValueError("latest_weeks_required must be at least 1.")


@dataclass(slots=True)
class WeeklyScreen:
    filename: str
    week_label: str
    week_date: date | None
    week_order: int
    dataframe: Any


@dataclass(slots=True)
class ConsensusResult:
    weekly_screens: list[WeeklyScreen]
    normalized_rows: Any
    stock_summary: Any
    weekly_top_five: Any
    consensus_top_five: Any
    next_week_candidates: Any
    portfolio_comparison: Any | None
    replacement_suggestions: Any | None
    dashboard_metrics: dict[str, Any] = field(default_factory=dict)
