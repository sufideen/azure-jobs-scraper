"""
Tests for scraper.generate_application_kits() — the orchestration around
utils/apply_kit.py: which jobs qualify, and graceful skipping when the
feature isn't configured. All Claude API calls are mocked.
"""
from unittest.mock import patch

import scraper as scraper_module
from scraper import Job, generate_application_kits


def _strong_job():
    # Mirrors utils/match.py's TestScoreJob fixtures — scores well into
    # "Strong" territory (IAM/Entra ID/PIM/Conditional Access/Zero Trust).
    return Job(
        title="IAM Architect",
        company="Lorien",
        location="London",
        salary_raw="£750/day",
        salary_min=165_000,
        salary_max=165_000,
        salary_type="daily",
        description="Entra ID, Conditional Access, PIM and Zero Trust experience needed.",
        url="https://example.com/job/iam",
        source="Reed",
        date_posted="",
        job_type="Contract",
    )


def _low_job():
    return Job(
        title="Trainee Network Engineer",
        company="Acme",
        location="London",
        salary_raw="£30,000",
        salary_min=30_000,
        salary_max=30_000,
        salary_type="annual",
        description="No experience needed, full training provided.",
        url="https://example.com/job/trainee",
        source="CW Jobs",
        date_posted="",
        job_type="Permanent",
    )


class TestGenerateApplicationKits:
    def test_skips_when_api_key_not_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = generate_application_kits([_strong_job()], tmp_path)
        assert result == []

    def test_skips_when_no_strong_matches(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        result = generate_application_kits([_low_job()], tmp_path)
        assert result == []

    def test_skips_when_cv_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setattr(scraper_module.Path, "exists", lambda self: False)
        result = generate_application_kits([_strong_job()], tmp_path)
        assert result == []

    def test_generates_and_saves_kit_for_strong_job(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setattr(scraper_module.Path, "exists", lambda self: True)
        monkeypatch.setattr(
            scraper_module.Path, "read_text",
            lambda self, encoding="utf-8": "MOCK CV TEXT",
        )

        job = _strong_job()
        with patch("anthropic.Anthropic") as mock_anthropic_cls, \
             patch(
                "utils.apply_kit.generate_application_kit",
                return_value="## CV Tweaks\n- x\n\n## Cover Letter\nDear Hiring Manager...",
             ) as mock_generate:
            result = generate_application_kits([job, _low_job()], tmp_path)

        mock_anthropic_cls.assert_called_once_with(api_key="sk-test-key")
        mock_generate.assert_called_once()
        assert len(result) == 1
        saved_path = result[0]
        # Path.exists/.read_text are monkeypatched above (to stub cv.txt),
        # so read the saved file via plain open() to check its real content.
        with open(saved_path, encoding="utf-8") as f:
            content = f.read()
        assert job.title in content
        assert job.company in content
        assert job.url in content
        assert "Cover Letter" in content

    def test_continues_after_one_job_fails(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setattr(scraper_module.Path, "exists", lambda self: True)
        monkeypatch.setattr(
            scraper_module.Path, "read_text",
            lambda self, encoding="utf-8": "MOCK CV TEXT",
        )

        job_a = _strong_job()
        job_b = _strong_job()
        job_b.title = "IAM Architect (Second Role)"
        job_b.url = "https://example.com/job/iam-2"

        with patch("anthropic.Anthropic"), \
             patch(
                "utils.apply_kit.generate_application_kit",
                side_effect=[RuntimeError("API error"), "## CV Tweaks\n- x\n\n## Cover Letter\nDear..."],
             ):
            result = generate_application_kits([job_a, job_b], tmp_path)

        # First job's failure is swallowed and logged; second still succeeds.
        assert len(result) == 1

    def test_slugify_used_for_filenames(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setattr(scraper_module.Path, "exists", lambda self: True)
        monkeypatch.setattr(
            scraper_module.Path, "read_text",
            lambda self, encoding="utf-8": "MOCK CV TEXT",
        )
        job = _strong_job()
        job.company = "Lorien & Co!"

        with patch("anthropic.Anthropic"), \
             patch("utils.apply_kit.generate_application_kit", return_value="body"):
            result = generate_application_kits([job], tmp_path)

        assert len(result) == 1
        filename = result[0].name
        assert filename.endswith(".md")
        assert " " not in filename
        assert "!" not in filename
        assert "&" not in filename
