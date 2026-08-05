from __future__ import annotations

import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.services.consensus.analysis_service import analyze_consensus
from app.services.consensus.excel_reader import (
    read_portfolio_files,
    read_weekly_files,
)
from app.services.consensus.excel_writer import build_workbook, output_filename
from app.services.consensus.models import ConsensusConfig


router = APIRouter(prefix="/api/consensus", tags=["Consensus Comparison"])


def build_automatic_config(total_files: int) -> ConsensusConfig:
    """
    Automatically determines all comparison settings from the number
    of uploaded weekly screening files.

    No scoring parameters are exposed to the user.
    """
    if total_files < 1:
        raise ValueError("Upload at least one filtered screening workbook.")

    # At least half the uploaded periods, but never fewer than two when
    # two or more files are supplied.
    minimum_frequency = max(
        1,
        min(total_files, max(2, round(total_files * 0.50))),
    )

    # Review the most recent 25% of periods, constrained to 1-4 files.
    latest_weeks_required = max(
        1,
        min(4, round(total_files * 0.25)),
    )

    return ConsensusConfig(
        top_n_per_industry=5,
        minimum_frequency=minimum_frequency,
        high_conviction_score=80.0,
        strong_candidate_score=68.0,
        latest_weeks_required=latest_weeks_required,

        # Automatic comparison weights.
        frequency_weight=0.25,
        average_rank_weight=0.15,
        rank_stability_weight=0.10,
        recency_weight=0.15,
        momentum_weight=0.10,
        technical_weight=0.10,
        trend_weight=0.05,
        volatility_weight=0.05,
        streak_weight=0.05,

        # Screening Service output is assumed to contain a volatility
        # quality score where a higher value is better.
        higher_volatility_score_is_better=True,
    )


@router.post("/analyze")
async def analyze_uploaded_files(
    filtered_files: list[UploadFile] = File(
        ...,
        description=(
            "Upload all filtered Screening Service Excel files. "
            "Select multiple files in this field."
        ),
    ),
    portfolio_files: list[UploadFile] | None = File(
        default=None,
        description=(
            "Optional: upload one or more portfolio Excel files. "
            "Select multiple files in this field."
        ),
    ),
):
    """
    Fully automatic comparison.

    The user provides only:
    1. Multiple filtered screening workbooks.
    2. Optional multiple portfolio workbooks.

    The service automatically:
    - sorts weekly files,
    - detects valid worksheets,
    - cleans company names and removes dividend values,
    - selects weekly top five stocks per sector and industry,
    - compares ranks, volatility, technical scores, trend scores,
      weighted returns, 6-month returns and 24-month returns,
    - calculates frequency, streak, rank stability, recency and momentum,
    - determines common and consistent stocks,
    - compares all supplied portfolios,
    - generates and downloads one formatted Excel workbook.
    """
    try:
        weekly_screens = await read_weekly_files(filtered_files)
        portfolio = await read_portfolio_files(portfolio_files)

        config = build_automatic_config(len(weekly_screens))

        result = analyze_consensus(
            weekly_screens=weekly_screens,
            portfolio=portfolio,
            config=config,
        )

        workbook = build_workbook(result, config)
        filename = output_filename()

        return StreamingResponse(
            io.BytesIO(workbook),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Uploaded-Files": str(result.dashboard_metrics["uploaded_files"]),
                "X-Common-Stocks": str(result.dashboard_metrics["common_stocks"]),
                "X-Every-Week-Stocks": str(
                    result.dashboard_metrics["every_week_stocks"]
                ),
                "X-Portfolio-Matches": str(
                    result.dashboard_metrics["portfolio_consensus_matches"]
                ),
                "Access-Control-Expose-Headers": (
                    "Content-Disposition, X-Uploaded-Files, X-Common-Stocks, "
                    "X-Every-Week-Stocks, X-Portfolio-Matches"
                ),
            },
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Consensus comparison failed: {exc}",
        ) from exc


@router.get("/health")
async def health():
    return {
        "service": "consensus-comparison",
        "status": "healthy",
        "input_fields": [
            "filtered_files",
            "portfolio_files",
        ],
    }
