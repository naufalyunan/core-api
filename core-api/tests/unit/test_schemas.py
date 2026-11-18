"""Fast tests: no database, no HTTP."""

import pytest
from pydantic import ValidationError

from app.schemas.ingestion import IntervalRow

VALID = {"hole_id": "DH-001", "from_m": 0, "to_m": 5, "lithology": "Sandstone", "rqd_pct": 85}


def test_valid_row() -> None:
    row = IntervalRow.model_validate(VALID)
    assert row.to_m == 5


def test_rqd_is_optional() -> None:
    assert IntervalRow.model_validate({**VALID, "rqd_pct": None}).rqd_pct is None


@pytest.mark.parametrize(
    "field,value",
    [("rqd_pct", 105), ("from_m", -2), ("lithology", ""), ("from_m", "abc")],
)
def test_invalid_row(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        IntervalRow.model_validate({**VALID, field: value})


@pytest.mark.parametrize("from_m,to_m", [(12, 12), (20, 15)])
def test_to_must_be_greater_than_from(from_m: float, to_m: float) -> None:
    with pytest.raises(ValidationError):
        IntervalRow.model_validate({**VALID, "from_m": from_m, "to_m": to_m})
