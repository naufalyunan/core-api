"""Validate an uploaded lithology CSV.

Pure Python: no database and no HTTP, so it's fast to unit test. The caller loads the
tenant's drillholes and existing intervals and passes them in.

Rules, checked in this order:
  1. file is UTF-8 and has the required columns          -> error on line 1
  2. each row on its own (types, ranges, to_m > from_m)    -> IntervalRow
  3. hole_id belongs to this organization                  -> holes dict is tenant-scoped
  4. to_m is not deeper than the drillhole's total depth
  5. no overlap with other rows in the file, or with intervals already stored

Line numbers match what a user sees in a spreadsheet: the header is line 1.
"""

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas.ingestion import IngestionError, IntervalRow

REQUIRED_COLUMNS = ("hole_id", "from_m", "to_m", "lithology", "rqd_pct")
MAX_ERRORS = 100


@dataclass(frozen=True)
class HoleInfo:
    id: uuid.UUID
    total_depth_m: float


@dataclass
class ValidationResult:
    rows_total: int = 0
    # Rows that passed the per-row checks, with their line numbers.
    rows: list[tuple[int, IntervalRow]] = field(default_factory=list)
    errors: list[IngestionError] = field(default_factory=list)

    @property
    def rows_valid(self) -> int:
        error_lines = {e.line for e in self.errors}
        return sum(1 for line, _ in self.rows if line not in error_lines)


def validate_csv(
    content: bytes,
    holes: dict[str, HoleInfo],
    existing_intervals: dict[str, list[tuple[float, float]]],
) -> ValidationResult:
    """Validate the whole file and return every row plus every error found.

    holes:              hole_id -> HoleInfo, ONLY for the uploader's organization.
    existing_intervals: hole_id -> [(from_m, to_m), ...] already stored for that hole.
    """
    result = ValidationResult()

    try:
        text = content.decode("utf-8-sig")  # -sig strips the BOM that Excel adds
    except UnicodeDecodeError:
        result.errors.append(IngestionError(line=1, message="File must be UTF-8 encoded CSV"))
        return result

    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        result.errors.append(
            IngestionError(line=1, message=f"Missing required columns: {', '.join(missing)}")
        )
        return result

    for line, raw in enumerate(reader, start=2):
        if not any((v or "").strip() for k, v in raw.items() if k is not None):
            continue  # skip blank lines
        result.rows_total += 1
        _check_row(line, raw, holes, result)

    _check_overlaps(result, existing_intervals)

    result.errors.sort(key=lambda e: e.line)
    if len(result.errors) > MAX_ERRORS:
        result.errors = result.errors[:MAX_ERRORS]
        result.errors.append(
            IngestionError(line=0, message=f"Too many errors; only the first {MAX_ERRORS} shown")
        )
    return result


def _check_row(
    line: int,
    raw: dict[str | None, str | None],
    holes: dict[str, HoleInfo],
    result: ValidationResult,
) -> None:
    data = {col: (raw.get(col) or "").strip() for col in REQUIRED_COLUMNS}
    # An empty RQD cell means "not measured" (e.g. loose gravel), not an error.
    values: dict[str, object] = {**data, "rqd_pct": data["rqd_pct"] or None}

    try:
        row = IntervalRow.model_validate(values)
    except ValidationError as exc:
        for err in exc.errors():
            # Field errors have loc=("from_m",); the to_m > from_m check has loc=().
            field_name = str(err["loc"][0]) if err["loc"] else "to_m"
            message = err["msg"].removeprefix("Value error, ")
            result.errors.append(IngestionError(line=line, field=field_name, message=message))
        return

    hole = holes.get(row.hole_id)
    if hole is None:
        # Same message whether the hole doesn't exist or belongs to another organization.
        result.errors.append(
            IngestionError(line=line, field="hole_id", message=f"Unknown drillhole {row.hole_id!r}")
        )
        return

    if row.to_m > hole.total_depth_m:
        result.errors.append(
            IngestionError(
                line=line,
                field="to_m",
                message=f"to_m {row.to_m:g} is deeper than the drillhole's total depth "
                f"{hole.total_depth_m:g} m",
            )
        )

    result.rows.append((line, row))


def _check_overlaps(
    result: ValidationResult, existing_intervals: dict[str, list[tuple[float, float]]]
) -> None:
    by_hole: dict[str, list[tuple[int, IntervalRow]]] = defaultdict(list)
    for line, row in result.rows:
        by_hole[row.hole_id].append((line, row))

    for hole_id, rows in by_hole.items():
        # Within the file: sort by depth, then each interval must start at or after the
        # previous one ends. Touching (5–12 then 12–20) is fine.
        rows.sort(key=lambda item: item[1].from_m)
        for (prev_line, prev), (line, row) in zip(rows, rows[1:], strict=False):
            if row.from_m < prev.to_m:
                result.errors.append(
                    IngestionError(
                        line=line,
                        field="from_m",
                        message=f"Overlaps {prev.from_m:g}–{prev.to_m:g} m on line {prev_line}",
                    )
                )

        # Against what's already stored (e.g. the same file uploaded twice).
        for line, row in rows:
            for start, end in existing_intervals.get(hole_id, []):
                if row.from_m < end and start < row.to_m:
                    result.errors.append(
                        IngestionError(
                            line=line,
                            field="from_m",
                            message=f"Overlaps existing interval {start:g}–{end:g} m",
                        )
                    )
                    break
