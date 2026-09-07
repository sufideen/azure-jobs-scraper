"""Tests for utils/match.py — CV keyword match scoring."""
from scraper import Job
from utils.match import match_label, score_job


def _job(title, description):
    return Job(
        title=title,
        company="Acme",
        location="London",
        salary_raw="£70,000",
        salary_min=70_000,
        salary_max=70_000,
        salary_type="annual",
        description=description,
        url="https://example.com",
        source="Reed",
        date_posted="",
        job_type="Permanent",
    )


class TestScoreJob:
    def test_core_skill_in_description_scores_positive(self):
        job = _job("Cloud Engineer", "Experience with Terraform and Bicep required.")
        assert score_job(job) > 0

    def test_core_skill_in_title_scores_higher_than_in_description(self):
        in_title = _job("Zero Trust Architect", "General IT role.")
        in_desc = _job("IT Architect", "Some Zero Trust experience helpful.")
        assert score_job(in_title) > score_job(in_desc)

    def test_no_keyword_overlap_scores_zero(self):
        job = _job("Marketing Manager", "Run social media campaigns.")
        assert score_job(job) == 0

    def test_service_desk_penalised(self):
        job = _job("1st Line Service Desk Engineer", "Support end users on the service desk.")
        assert score_job(job) < 0

    def test_software_developer_penalised(self):
        job = _job("Software Engineer - React", "Build React front-end applications.")
        assert score_job(job) < 0

    def test_strong_iam_role_scores_highly(self):
        job = _job(
            "IAM Architect",
            "Entra ID, Conditional Access, PIM and Zero Trust experience needed.",
        )
        assert score_job(job) >= 12


class TestMatchLabel:
    def test_high_score_is_strong(self):
        assert match_label(20) == "Strong"

    def test_boundary_12_is_strong(self):
        assert match_label(12) == "Strong"

    def test_mid_score_is_good(self):
        assert match_label(7) == "Good"

    def test_low_positive_score_is_fair(self):
        assert match_label(1) == "Fair"

    def test_zero_is_low(self):
        assert match_label(0) == "Low"

    def test_negative_is_low(self):
        assert match_label(-5) == "Low"
