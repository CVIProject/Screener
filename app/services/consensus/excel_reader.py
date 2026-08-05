from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

from app.services.consensus.cleaning import (
    parse_portfolio_model_matrix,
    standardize_portfolio_dataframe,
    standardize_screening_dataframe,
)
from app.services.consensus.models import WeeklyScreen


DATE_PATTERNS = (
    r"(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})",
    r"(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})",
)


def detect_date_from_filename(filename: str) -> date | None:
    stem = Path(filename).stem
    for index, pattern in enumerate(DATE_PATTERNS):
        match = re.search(pattern, stem)
        if not match:
            continue
        parts = match.groups()
        try:
            if index == 0:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
        except ValueError:
            continue
    return None


def _read_screening_workbook(content: bytes, filename: str) -> pd.DataFrame:
    workbook = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
    errors: list[str] = []

    for sheet_name in workbook.sheet_names:
        try:
            candidate = pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet_name,
                engine="openpyxl",
            )
            return standardize_screening_dataframe(
                candidate,
                f"{filename} [{sheet_name}]",
            )
        except Exception as exc:
            errors.append(f"{sheet_name}: {exc}")

    raise ValueError(
        f"{filename}: no worksheet contains a valid screening output. "
        + " | ".join(errors[:5])
    )


def _read_portfolio_workbook(content: bytes, filename: str) -> pd.DataFrame:
    workbook = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
    errors: list[str] = []

    for sheet_name in workbook.sheet_names:
        source_name = f"{filename} [{sheet_name}]"

        # Format 1: standard row-based table.
        try:
            table = pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet_name,
                engine="openpyxl",
            )
            parsed = standardize_portfolio_dataframe(table, source_name)
            if not parsed.empty:
                parsed["source_sheet"] = sheet_name
                parsed["portfolio_format"] = "row_table"
                return parsed
        except Exception as exc:
            errors.append(f"{sheet_name} row-table: {exc}")

        # Format 2: model matrix with portfolio names across columns.
        try:
            raw = pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet_name,
                header=None,
                engine="openpyxl",
            )
            parsed = parse_portfolio_model_matrix(raw, source_name)
            if not parsed.empty:
                parsed["source_sheet"] = sheet_name
                parsed["portfolio_format"] = "model_matrix"
                return parsed
        except Exception as exc:
            errors.append(f"{sheet_name} model-matrix: {exc}")

    raise ValueError(
        f"{filename}: no worksheet contains a supported portfolio format. "
        "Supported formats are a row-based ticker table or a model matrix "
        "with portfolio names across columns and Symbol rows. "
        + " | ".join(errors[:8])
    )


async def read_weekly_files(files: list[UploadFile]) -> list[WeeklyScreen]:
    if not files:
        raise ValueError("Upload at least one filtered screening workbook.")

    items: list[tuple[int, str, date | None, pd.DataFrame]] = []

    for upload_index, upload in enumerate(files):
        filename = upload.filename or f"week_{upload_index + 1}.xlsx"
        if not filename.lower().endswith((".xlsx", ".xlsm")):
            raise ValueError(f"{filename}: only .xlsx and .xlsm are supported.")

        content = await upload.read()
        if not content:
            raise ValueError(f"{filename}: uploaded file is empty.")

        dataframe = _read_screening_workbook(content, filename)
        items.append(
            (
                upload_index,
                filename,
                detect_date_from_filename(filename),
                dataframe,
            )
        )

    dated = [item for item in items if item[2] is not None]
    undated = [item for item in items if item[2] is None]
    dated.sort(key=lambda item: (item[2], item[0]))
    undated.sort(key=lambda item: item[0])
    ordered = dated + undated if dated else undated

    result: list[WeeklyScreen] = []
    for week_order, (_, filename, week_date, dataframe) in enumerate(ordered, start=1):
        result.append(
            WeeklyScreen(
                filename=filename,
                week_label=week_date.isoformat() if week_date else f"Week {week_order}",
                week_date=week_date,
                week_order=week_order,
                dataframe=dataframe,
            )
        )
    return result


async def read_portfolio_files(
    uploads: list[UploadFile] | None,
) -> pd.DataFrame | None:
    if not uploads:
        return None

    frames: list[pd.DataFrame] = []

    for upload in uploads:
        filename = upload.filename or "portfolio.xlsx"
        if not filename.lower().endswith((".xlsx", ".xlsm")):
            raise ValueError(
                f"{filename}: only .xlsx and .xlsm portfolio files are supported."
            )

        content = await upload.read()
        if not content:
            continue

        dataframe = _read_portfolio_workbook(content, filename)
        default_portfolio_name = Path(filename).stem

        dataframe["portfolio_name"] = (
            dataframe["portfolio_name"]
            .fillna(default_portfolio_name)
            .astype(str)
            .str.strip()
        )
        dataframe.loc[
            dataframe["portfolio_name"].eq(""),
            "portfolio_name",
        ] = default_portfolio_name

        dataframe["source_portfolio_file"] = filename
        frames.append(dataframe)

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(
        subset=["ticker", "portfolio_name"],
        keep="first",
    ).reset_index(drop=True)
