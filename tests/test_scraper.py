"""
Tests for scraper.py

Covers:
  - Job dataclass      — field presence, default dedup_key, instantiation
  - CSV_FIELDNAMES     — all expected columns present, dedup_key excluded
  - save_to_csv()      — file creation, header row, data rows
  - build_html_report() — HTML structure, job data inclusion, sorting
  - Reed HTML parser   — _extract_jobs() integration via sample fixture
  - CW Jobs parser     — extract_jobs_from_page() integration via sample fixture
"""
import csv
import os

import pytest

from scraper import CSV_FIELDNAMES, Job, build_html_report, save_to_csv


# ── Job dataclass ─────────────────────────────────────────────────────────────

class TestJobDataclass:
    def test_job_can_be_instantiated(self, mock_job):
        assert mock_job.title == "Azure Infrastructure Engineer"

    def test_dedup_key_defaults_to_empty_string(self):
        job = Job(
            title="Test", company="Co", location="London",
            salary_raw="£60k", salary_min=60_000, salary_max=60_000,
            salary_type="annual", description="Desc", url="https://example.com",
            source="Reed", date_posted="2026-02-25T00:00:00Z", job_type="Permanent",
        )
        assert job.dedup_key == ""

    def test_all_expected_fields_accessible(self, mock_job):
        assert hasattr(mock_job, "title")
        assert hasattr(mock_job, "company")
        assert hasattr(mock_job, "location")
        assert hasattr(mock_job, "salary_raw")
        assert hasattr(mock_job, "salary_min")
        assert hasattr(mock_job, "salary_max")
        assert hasattr(mock_job, "salary_type")
        assert hasattr(mock_job, "description")
        assert hasattr(mock_job, "url")
        assert hasattr(mock_job, "source")
        assert hasattr(mock_job, "date_posted")
        assert hasattr(mock_job, "job_type")
        assert hasattr(mock_job, "dedup_key")

    def test_none_salary_allowed(self, mock_unknown_salary_job):
        assert mock_unknown_salary_job.salary_min is None
        assert mock_unknown_salary_job.salary_max is None


# ── CSV_FIELDNAMES ────────────────────────────────────────────────────────────

class TestCsvFieldnames:
    def test_dedup_key_excluded(self):
        assert "dedup_key" not in CSV_FIELDNAMES

    def test_expected_columns_present(self):
        for col in ("title", "company", "location", "salary_raw",
                    "salary_min", "salary_max", "salary_type",
                    "description", "url", "source", "date_posted", "job_type"):
            assert col in CSV_FIELDNAMES

    def test_fieldnames_is_list(self):
        assert isinstance(CSV_FIELDNAMES, list)


# ── save_to_csv ───────────────────────────────────────────────────────────────

class TestSaveToCsv:
    def test_creates_file(self, tmp_path, mock_job):
        filepath = str(tmp_path / "jobs.csv")
        save_to_csv([mock_job], filepath)
        assert os.path.exists(filepath)

    def test_header_row_present(self, tmp_path, mock_job):
        filepath = str(tmp_path / "jobs.csv")
        save_to_csv([mock_job], filepath)
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "title" in reader.fieldnames
            assert "salary_min" in reader.fieldnames

    def test_data_row_written(self, tmp_path, mock_job):
        filepath = str(tmp_path / "jobs.csv")
        save_to_csv([mock_job], filepath)
        with open(filepath, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["title"] == "Azure Infrastructure Engineer"
        assert rows[0]["source"] == "Reed"

    def test_multiple_jobs_written(self, tmp_path, mock_job, mock_contract_job):
        filepath = str(tmp_path / "jobs.csv")
        save_to_csv([mock_job, mock_contract_job], filepath)
        with open(filepath, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_empty_list_creates_header_only(self, tmp_path):
        filepath = str(tmp_path / "empty.csv")
        save_to_csv([], filepath)
        with open(filepath, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows == []

    def test_unknown_salary_written_as_empty(self, tmp_path, mock_unknown_salary_job):
        filepath = str(tmp_path / "jobs.csv")
        save_to_csv([mock_unknown_salary_job], filepath)
        with open(filepath, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["salary_min"] == ""
        assert rows[0]["salary_max"] == ""


# ── build_html_report ─────────────────────────────────────────────────────────

class TestBuildHtmlReport:
    def test_returns_string(self, mock_job):
        html = build_html_report([mock_job])
        assert isinstance(html, str)

    def test_contains_doctype(self, mock_job):
        html = build_html_report([mock_job])
        assert "<!DOCTYPE html>" in html

    def test_contains_job_title(self, mock_job):
        html = build_html_report([mock_job])
        assert "Azure Infrastructure Engineer" in html

    def test_contains_job_url(self, mock_job):
        html = build_html_report([mock_job])
        assert mock_job.url in html

    def test_contains_azure_header(self, mock_job):
        html = build_html_report([mock_job])
        assert "Azure Jobs Report" in html

    def test_session_label_included(self, mock_job):
        html = build_html_report([mock_job], session_label="Morning Report")
        assert "Morning Report" in html

    def test_job_count_in_header(self, mock_job, mock_contract_job):
        html = build_html_report([mock_job, mock_contract_job])
        assert "2 jobs" in html

    def test_sorted_by_salary_descending(self, mock_job, mock_contract_job):
        # mock_contract_job has salary_max=132,000; mock_job has salary_max=85,000
        html = build_html_report([mock_job, mock_contract_job])
        idx_contract = html.index("Azure Platform Engineer")
        idx_perm = html.index("Azure Infrastructure Engineer")
        assert idx_contract < idx_perm  # higher salary appears first

    def test_empty_jobs_list(self):
        html = build_html_report([])
        assert "0 jobs" in html

    def test_html_entities_escaped(self):
        job = Job(
            title="Azure & Cloud Engineer <Senior>",
            company="Acme & Sons",
            location="London",
            salary_raw="£70,000",
            salary_min=70_000,
            salary_max=70_000,
            salary_type="annual",
            description="Work with <b>Azure</b> & AWS.",
            url="https://example.com",
            source="Reed",
            date_posted="2026-02-25T00:00:00Z",
            job_type="Permanent",
        )
        html = build_html_report([job])
        assert "<Senior>" not in html   # raw < > must be escaped
        assert "&lt;Senior&gt;" in html


# ── Reed scraper integration ──────────────────────────────────────────────────

class TestReedScraper:
    def test_parses_job_from_fixture(self, sample_html_reed):
        from scrapers.reed import _extract_jobs
        jobs = _extract_jobs(sample_html_reed)
        assert len(jobs) == 1
        assert jobs[0].title == "Azure Cloud Engineer"
        assert jobs[0].source == "Reed"

    def test_excludes_sc_cleared(self, sample_html_reed_sc_cleared):
        from scrapers.reed import _extract_jobs
        jobs = _extract_jobs(sample_html_reed_sc_cleared)
        assert jobs == []

    def test_returns_empty_on_missing_next_data(self):
        from scrapers.reed import _extract_jobs
        jobs = _extract_jobs("<html><body>No data here</body></html>")
        assert jobs == []


# ── CW Jobs scraper integration ───────────────────────────────────────────────

class TestCwJobsScraper:
    def test_parses_job_from_fixture(self, sample_html_cwjobs):
        from scrapers.cwjobs import extract_jobs_from_page
        jobs = extract_jobs_from_page(sample_html_cwjobs, "CW Jobs", "https://www.cwjobs.co.uk")
        assert len(jobs) == 1
        assert jobs[0].title == "Azure Network Engineer"
        assert jobs[0].source == "CW Jobs"

    def test_returns_empty_on_missing_state(self):
        from scrapers.cwjobs import extract_jobs_from_page
        html = "<html><body>Nothing here</body></html>"
        jobs = extract_jobs_from_page(html, "CW Jobs", "https://www.cwjobs.co.uk")
        assert jobs == []
