"""
Tests for utils/dedup.py

Covers:
  - make_dedup_key()     — consistent MD5 hashing, normalisation
  - deduplicate_jobs()   — collision resolution, salary preference, description preference
"""
import pytest

from scraper import Job
from utils.dedup import deduplicate_jobs, make_dedup_key


def _make_job(title="Azure Engineer", company="Acme", location="London",
              sal_min=60_000, sal_max=80_000, description="Short desc.",
              source="Reed", url="https://example.com/1"):
    """Helper to create a minimal Job for dedup tests."""
    j = Job(
        title=title,
        company=company,
        location=location,
        salary_raw=f"£{sal_min}–£{sal_max}",
        salary_min=sal_min,
        salary_max=sal_max,
        salary_type="annual",
        description=description,
        url=url,
        source=source,
        date_posted="2026-02-25T10:00:00Z",
        job_type="Permanent",
    )
    from utils.dedup import make_dedup_key as mdk
    j.dedup_key = mdk(title, company, location)
    return j


# ── make_dedup_key ────────────────────────────────────────────────────────────

class TestMakeDedupKey:
    def test_same_inputs_same_key(self):
        k1 = make_dedup_key("Azure Engineer", "Acme", "London")
        k2 = make_dedup_key("Azure Engineer", "Acme", "London")
        assert k1 == k2

    def test_different_titles_different_keys(self):
        k1 = make_dedup_key("Azure Engineer", "Acme", "London")
        k2 = make_dedup_key("Azure Architect", "Acme", "London")
        assert k1 != k2

    def test_different_companies_different_keys(self):
        k1 = make_dedup_key("Azure Engineer", "Acme", "London")
        k2 = make_dedup_key("Azure Engineer", "BetaCorp", "London")
        assert k1 != k2

    def test_different_locations_different_keys(self):
        k1 = make_dedup_key("Azure Engineer", "Acme", "London")
        k2 = make_dedup_key("Azure Engineer", "Acme", "Manchester")
        assert k1 != k2

    def test_case_insensitive_normalisation(self):
        k1 = make_dedup_key("AZURE ENGINEER", "ACME", "LONDON")
        k2 = make_dedup_key("azure engineer", "acme", "london")
        assert k1 == k2

    def test_punctuation_normalised(self):
        k1 = make_dedup_key("Azure Engineer (Senior)", "Acme Ltd.", "London, UK")
        k2 = make_dedup_key("Azure Engineer  Senior", "Acme Ltd", "London  UK")
        assert k1 == k2

    def test_returns_hex_string(self):
        key = make_dedup_key("Azure Engineer", "Acme", "London")
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


# ── deduplicate_jobs ──────────────────────────────────────────────────────────

class TestDeduplicateJobs:
    def test_unique_jobs_unchanged(self):
        jobs = [
            _make_job(title="Azure Engineer", url="https://example.com/1"),
            _make_job(title="Azure Architect", company="BetaCorp", url="https://example.com/2"),
        ]
        result = deduplicate_jobs(jobs)
        assert len(result) == 2

    def test_exact_duplicate_removed(self):
        j1 = _make_job(url="https://example.com/1")
        j2 = _make_job(url="https://example.com/2")  # same title/company/location
        result = deduplicate_jobs([j1, j2])
        assert len(result) == 1

    def test_prefers_known_salary_over_unknown(self):
        j_unknown = _make_job(sal_min=None, sal_max=None,
                              url="https://example.com/1")
        j_unknown.salary_min = None
        j_unknown.salary_max = None
        j_known = _make_job(sal_min=70_000, sal_max=85_000,
                            url="https://example.com/2")
        result = deduplicate_jobs([j_unknown, j_known])
        assert len(result) == 1
        assert result[0].salary_min == 70_000

    def test_prefers_longer_description_same_salary_status(self):
        j_short = _make_job(description="Short.", url="https://example.com/1")
        j_long = _make_job(
            description="A much longer description with far more detail about the role.",
            url="https://example.com/2",
        )
        result = deduplicate_jobs([j_short, j_long])
        assert len(result) == 1
        assert "much longer" in result[0].description

    def test_empty_list_returns_empty(self):
        assert deduplicate_jobs([]) == []

    def test_single_job_returned(self):
        jobs = [_make_job()]
        result = deduplicate_jobs(jobs)
        assert len(result) == 1

    def test_order_first_seen_wins_when_equal(self):
        j1 = _make_job(description="Same length desc!", url="https://example.com/1")
        j2 = _make_job(description="Also same length.", url="https://example.com/2")
        result = deduplicate_jobs([j1, j2])
        assert result[0].url == "https://example.com/1"
