"""
Tests for utils/salary.py

Covers:
  - parse_salary()  — annual, daily, k-shorthand, unknown, edge cases
  - salary_passes_filter()  — threshold logic, unknown salary pass-through
  - format_salary_display()  — human-readable output
"""
import pytest

from utils.salary import (
    WORKING_DAYS_PER_YEAR,
    format_salary_display,
    parse_salary,
    salary_passes_filter,
)


# ── parse_salary ──────────────────────────────────────────────────────────────

class TestParseSalaryAnnual:
    def test_plain_range(self):
        sal_min, sal_max, sal_type = parse_salary("£60,000 - £80,000 per annum")
        assert sal_min == 60_000
        assert sal_max == 80_000
        assert sal_type == "annual"

    def test_k_shorthand_range(self):
        sal_min, sal_max, sal_type = parse_salary("60k - 80k")
        assert sal_min == 60_000
        assert sal_max == 80_000
        assert sal_type == "annual"

    def test_single_value(self):
        sal_min, sal_max, sal_type = parse_salary("£75,000 per annum")
        assert sal_min == 75_000
        assert sal_max == 75_000
        assert sal_type == "annual"

    def test_per_year_keyword(self):
        sal_min, sal_max, sal_type = parse_salary("55000 per year")
        assert sal_type == "annual"
        assert sal_min == 55_000

    def test_large_range_inferred_annual(self):
        # Values >= 2000 without daily keyword → annual
        sal_min, sal_max, sal_type = parse_salary("£90,000 - £110,000")
        assert sal_type == "annual"
        assert sal_min == 90_000
        assert sal_max == 110_000

    def test_min_greater_than_max_swapped(self):
        # If raw string gives max before min, values are swapped
        sal_min, sal_max, sal_type = parse_salary("£80,000 - £60,000")
        assert sal_min == 60_000
        assert sal_max == 80_000


class TestParseSalaryDaily:
    def test_explicit_per_day(self):
        sal_min, sal_max, sal_type = parse_salary("£450 - £550 per day")
        assert sal_type == "daily"
        assert sal_min == 450 * WORKING_DAYS_PER_YEAR
        assert sal_max == 550 * WORKING_DAYS_PER_YEAR

    def test_slash_day_notation(self):
        sal_min, sal_max, sal_type = parse_salary("£500/day")
        assert sal_type == "daily"
        assert sal_min == 500 * WORKING_DAYS_PER_YEAR

    def test_small_values_heuristic(self):
        # Values < 2000 without annual keyword → treated as daily
        sal_min, sal_max, sal_type = parse_salary("£400 - £600")
        assert sal_type == "daily"
        assert sal_min == 400 * WORKING_DAYS_PER_YEAR
        assert sal_max == 600 * WORKING_DAYS_PER_YEAR

    def test_p_d_notation(self):
        sal_min, sal_max, sal_type = parse_salary("500 p/d")
        assert sal_type == "daily"

    def test_daily_rate_keyword(self):
        sal_min, sal_max, sal_type = parse_salary("day rate £600")
        assert sal_type == "daily"


class TestParseSalaryUnknown:
    def test_empty_string(self):
        sal_min, sal_max, sal_type = parse_salary("")
        assert sal_min is None
        assert sal_max is None
        assert sal_type == "unknown"

    def test_none_input(self):
        sal_min, sal_max, sal_type = parse_salary(None)
        assert sal_min is None
        assert sal_type == "unknown"

    def test_whitespace_only(self):
        sal_min, sal_max, sal_type = parse_salary("   ")
        assert sal_type == "unknown"

    def test_no_numbers(self):
        sal_min, sal_max, sal_type = parse_salary("Competitive salary")
        assert sal_type == "unknown"

    def test_numbers_below_100_ignored(self):
        # All extracted numbers < 100 should be ignored → unknown
        sal_min, sal_max, sal_type = parse_salary("Band 6 – Grade 8")
        assert sal_type == "unknown"


# ── salary_passes_filter ──────────────────────────────────────────────────────

class TestSalaryPassesFilter:
    def test_above_threshold(self):
        assert salary_passes_filter(60_000, 80_000) is True

    def test_exactly_at_threshold(self):
        assert salary_passes_filter(50_000, 50_000) is True

    def test_below_threshold(self):
        assert salary_passes_filter(30_000, 45_000) is False

    def test_unknown_salary_passes(self):
        # Unknown salary must pass — benefit of the doubt
        assert salary_passes_filter(None, None) is True

    def test_only_max_provided(self):
        assert salary_passes_filter(None, 55_000) is True

    def test_only_max_below_threshold(self):
        assert salary_passes_filter(None, 40_000) is False

    def test_custom_threshold(self):
        assert salary_passes_filter(45_000, 55_000, threshold=60_000) is False
        assert salary_passes_filter(65_000, 75_000, threshold=60_000) is True


# ── format_salary_display ─────────────────────────────────────────────────────

class TestFormatSalaryDisplay:
    def test_annual_range(self):
        result = format_salary_display(60_000, 80_000, "annual", "raw")
        assert "60,000" in result
        assert "80,000" in result

    def test_annual_single(self):
        result = format_salary_display(75_000, 75_000, "annual", "raw")
        assert "75,000" in result

    def test_daily_range(self):
        sal_min = 450 * WORKING_DAYS_PER_YEAR
        sal_max = 550 * WORKING_DAYS_PER_YEAR
        result = format_salary_display(sal_min, sal_max, "daily", "raw")
        assert "/day" in result
        assert "450" in result
        assert "550" in result

    def test_unknown_falls_back_to_raw(self):
        result = format_salary_display(None, None, "unknown", "Not specified")
        assert result == "Not specified"

    def test_unknown_empty_raw(self):
        result = format_salary_display(None, None, "unknown", "")
        assert result == "Not specified"
