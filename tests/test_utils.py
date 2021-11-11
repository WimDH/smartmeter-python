import pytest
from app.utils import convert_from_human_readable, autoformat, calculate_timestamp_drift


@pytest.mark.parametrize(
    "in_value, out_value",
    [
        (1000, 1000),
        ("1010", 1010),
        ("10k", 10240),
        ("10M", 10485760),
        ("10G", 10737418240),
    ],
)
def test_convert_from_human_readable(in_value, out_value) -> None:
    """Test the conversion of ex. 10k to 10240."""
    assert convert_from_human_readable(in_value) == out_value


def test_convert_from_human_readable_fail() -> None:
    """Test when the conversion fails."""
    with pytest.raises(ValueError):
        assert convert_from_human_readable("10m")


@pytest.mark.parametrize(
    "in_value, out_value",
    [
        (1000, 1000),
        ("aaa", "aaa"),
        ("1010", 1010),
        ("10.12", 10.12),
    ],
)
def test_autoformat(in_value, out_value) -> None:
    """Test the autoformat function."""
    assert autoformat(in_value) == out_value


def test_calculate_timestamp_drift():
    """Crappy test"""

    result = calculate_timestamp_drift("tata", "2021-11-07T17:57:35+01:00")

    assert result > 0
