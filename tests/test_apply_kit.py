"""
Tests for utils/apply_kit.py — Claude API call for CV tweaks + cover letter.

All API calls are mocked with unittest.mock — no real network requests,
and no Anthropic API key or spend needed to run this suite.
"""
from unittest.mock import MagicMock

from scraper import Job
from utils.apply_kit import generate_application_kit


def _job():
    return Job(
        title="IAM Architect",
        company="Lorien",
        location="London",
        salary_raw="£750/day",
        salary_min=165_000,
        salary_max=165_000,
        salary_type="daily",
        description="Entra ID, PIM and Conditional Access experience needed.",
        url="https://example.com/job/1",
        source="Reed",
        date_posted="2026-09-01T00:00:00Z",
        job_type="Contract",
    )


def _mock_client(response_text: str) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = response_text

    response = MagicMock()
    response.content = [text_block]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


class TestGenerateApplicationKit:
    def test_returns_text_from_response(self):
        client = _mock_client("## CV Tweaks\n- Lead with IAM work\n\n## Cover Letter\nDear...")
        result = generate_application_kit(client, "CV TEXT HERE", _job())
        assert "CV Tweaks" in result
        assert "Cover Letter" in result

    def test_ignores_non_text_blocks(self):
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.text = "internal reasoning"

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "final answer"

        response = MagicMock()
        response.content = [thinking_block, text_block]
        client = MagicMock()
        client.messages.create.return_value = response

        result = generate_application_kit(client, "CV TEXT HERE", _job())
        assert result == "final answer"
        assert "internal reasoning" not in result

    def test_passes_job_details_to_the_api_call(self):
        client = _mock_client("output")
        job = _job()
        generate_application_kit(client, "MY CV", job)

        _, kwargs = client.messages.create.call_args
        user_content = kwargs["messages"][0]["content"]
        assert "MY CV" in user_content
        assert job.title in user_content
        assert job.company in user_content
        assert job.description in user_content

    def test_raises_on_api_error(self):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("API down")
        try:
            generate_application_kit(client, "CV TEXT HERE", _job())
            assert False, "expected RuntimeError to propagate"
        except RuntimeError:
            pass
