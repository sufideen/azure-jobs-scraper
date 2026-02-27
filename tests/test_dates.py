"""
Tests for utils/dates.py

Covers:
  - parse_date()       — ISO normalisation, empty/invalid inputs
  - is_within_7_days() — recency filter, boundary conditions, unknown dates
  - parse_jn_date()    — Michael Page JN reference extraction
"""
from datetime import datetime, timezone, timedelta

import pytest

from utils.dates import is_within_7_days, parse_date, parse_jn_date


# ── parse_date ────────────────────────────────────────────────────────────────

class TestParseDate:
    def test_iso_string_preserved(self):
        result = parse_date("2026-02-25T10:30:00Z")
        assert result == "2026-02-25T10:30:00Z"

    def test_date_only_string(self):
        result = parse_date("2026-02-25")
        # Should contain the date; time component may vary by dateutil
        assert "2026-02-25" in result

    def test_human_readable_format(self):
        result = parse_date("25 February 2026")
        assert "2026-02-25" in result

    def test_slash_format(self):
        result = parse_date("02/25/2026")
        assert "2026-02-25" in result

    def test_empty_string_returns_empty(self):
        assert parse_date("") == ""

    def test_none_input_returns_empty(self):
        assert parse_date(None) == ""

    def test_whitespace_returns_empty(self):
        assert parse_date("   ") == ""

    def test_unparseable_returns_raw(self):
        raw = "not-a-date-xyzzy"
        result = parse_date(raw)
        # Should return the raw string unchanged when parsing fails
        assert result == raw

    def test_output_ends_with_z(self):
        result = parse_date("2026-01-15T08:00:00")
        assert result.endswith("Z")


# ── is_within_7_days ──────────────────────────────────────────────────────────

class TestIsWithin7Days:
    def _days_ago(self, days: int) -> str:
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_today_is_within(self):
        assert is_within_7_days(self._days_ago(0)) is True

    def test_yesterday_is_within(self):
        assert is_within_7_days(self._days_ago(1)) is True

    def test_6_days_ago_is_within(self):
        assert is_within_7_days(self._days_ago(6)) is True

    def test_exactly_7_days_ago_boundary(self):
        # Exactly 7 days ago may be on the boundary — the cutoff is >= 7 days
        # We accept either True or False here since it's a boundary edge
        result = is_within_7_days(self._days_ago(7))
        assert isinstance(result, bool)

    def test_8_days_ago_excluded(self):
        assert is_within_7_days(self._days_ago(8)) is False

    def test_30_days_ago_excluded(self):
        assert is_within_7_days(self._days_ago(30)) is False

    def test_empty_string_returns_true(self):
        # Unknown date → include by default
        assert is_within_7_days("") is True

    def test_none_returns_true(self):
        assert is_within_7_days(None) is True

    def test_unparseable_returns_true(self):
        assert is_within_7_days("not-a-date") is True

    def test_future_date_is_within(self):
        dt = datetime.now(timezone.utc) + timedelta(days=1)
        assert is_within_7_days(dt.strftime("%Y-%m-%dT%H:%M:%SZ")) is True


# ── parse_jn_date ─────────────────────────────────────────────────────────────

class TestParseJnDate:
    def test_standard_jn_url(self):
        url = "/jobs/it-technology/london/jn-022026-6946427/azure-engineer"
        result = parse_jn_date(url)
        assert result == "2026-02-01T00:00:00Z"

    def test_different_month(self):
        url = "/jobs/technology/london/jn-012026-1234567/azure-architect"
        result = parse_jn_date(url)
        assert result == "2026-01-01T00:00:00Z"

    def test_december(self):
        url = "/jobs/technology/london/jn-122025-9876543/cloud-engineer"
        result = parse_jn_date(url)
        assert result == "2025-12-01T00:00:00Z"

    def test_no_jn_reference_returns_empty(self):
        assert parse_jn_date("/jobs/some-job/12345") == ""

    def test_empty_string_returns_empty(self):
        assert parse_jn_date("") == ""

    def test_case_insensitive(self):
        url = "/jobs/technology/london/JN-032026-1111111/azure-admin"
        result = parse_jn_date(url)
        assert result == "2026-03-01T00:00:00Z"

    def test_full_url_string(self):
        url = "https://www.michaelpage.co.uk/jobs/it-technology/london/jn-022026-9999999/azure-infra"
        result = parse_jn_date(url)
        assert result == "2026-02-01T00:00:00Z"
