"""CSV validation rules, tested without a database."""

import uuid
from pathlib import Path

from app.services.ingestion_validation import HoleInfo, validate_csv

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
HEADER = "hole_id,from_m,to_m,lithology,rqd_pct\n"
HOLES = {"DH-001": HoleInfo(uuid.uuid4(), 60), "DH-002": HoleInfo(uuid.uuid4(), 45)}


def errors_by_line(content: bytes, existing: dict | None = None) -> dict[int, list[str | None]]:
    result = validate_csv(content, HOLES, existing or {})
    out: dict[int, list[str | None]] = {}
    for e in result.errors:
        out.setdefault(e.line, []).append(e.field)
    return out


def test_valid_sample_file_has_no_errors() -> None:
    result = validate_csv((SAMPLES / "intervals_red_ridge_valid.csv").read_bytes(), HOLES, {})
    assert result.errors == []
    assert result.rows_total == result.rows_valid == 11


def test_invalid_sample_file_reports_every_bad_line() -> None:
    errors = errors_by_line((SAMPLES / "intervals_red_ridge_invalid.csv").read_bytes())
    assert errors == {
        3: ["from_m"],  # overlaps line 2
        4: ["to_m"],  # to_m == from_m
        5: ["to_m"],  # to_m < from_m
        6: ["rqd_pct"],  # 105 > 100
        7: ["from_m", "to_m"],  # negative from_m, to_m of 0
        8: ["lithology"],  # empty
        9: ["to_m"],  # 52 m in a 45 m hole
        10: ["hole_id"],  # DH-003 belongs to another organization
        11: ["hole_id"],  # DH-999 doesn't exist
        12: ["from_m"],  # "abc"
    }


def test_touching_intervals_are_not_overlaps() -> None:
    csv = HEADER + "DH-001,0,5,Sandstone,80\nDH-001,5,12,Shale,60\n"
    assert errors_by_line(csv.encode()) == {}


def test_rows_out_of_order_are_still_checked_for_overlap() -> None:
    csv = HEADER + "DH-001,10,20,Shale,60\nDH-001,0,12,Sandstone,80\n"
    assert errors_by_line(csv.encode()) == {2: ["from_m"]}


def test_overlap_with_existing_intervals() -> None:
    csv = HEADER + "DH-001,0,5,Sandstone,80\n"
    assert errors_by_line(csv.encode(), {"DH-001": [(3.0, 8.0)]}) == {2: ["from_m"]}


def test_empty_rqd_is_allowed() -> None:
    csv = HEADER + "DH-001,0,5,Gravel,\n"
    assert errors_by_line(csv.encode()) == {}


def test_missing_columns_reported_on_header_line() -> None:
    result = validate_csv(b"hole_id,from_m\nDH-001,0\n", HOLES, {})
    assert [e.line for e in result.errors] == [1]
    assert "to_m" in result.errors[0].message


def test_excel_bom_is_accepted() -> None:
    csv = "﻿" + HEADER + "DH-001,0,5,Sandstone,80\n"
    assert errors_by_line(csv.encode("utf-8")) == {}


def test_blank_lines_are_ignored() -> None:
    csv = HEADER + "DH-001,0,5,Sandstone,80\n,,,,\n\nDH-001,5,9,Shale,70\n"
    result = validate_csv(csv.encode(), HOLES, {})
    assert result.errors == []
    assert result.rows_total == 2
