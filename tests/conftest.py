"""
Shared pytest fixtures for the Azure Jobs Scraper test suite.

sys.path is patched here so that `from scraper import Job` and
`from utils.xxx import ...` resolve when pytest is run from the project root.
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so all imports resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402 — must come after sys.path fix

from scraper import Job  # noqa: E402


@pytest.fixture
def mock_job():
    """A fully-populated Job fixture used across multiple test modules."""
    return Job(
        title="Azure Infrastructure Engineer",
        company="Acme Cloud Ltd",
        location="London",
        salary_raw="£70,000–£85,000 per annum",
        salary_min=70_000,
        salary_max=85_000,
        salary_type="annual",
        description="Design and maintain Azure infrastructure using Terraform and ARM templates.",
        url="https://www.reed.co.uk/jobs/azure-infrastructure-engineer/12345678",
        source="Reed",
        date_posted="2026-02-25T10:00:00Z",
        job_type="Permanent",
    )


@pytest.fixture
def mock_contract_job():
    """A contract/daily-rate Job fixture."""
    return Job(
        title="Azure Platform Engineer",
        company="TechCorp",
        location="City of London",
        salary_raw="£500–£600/day",
        salary_min=110_000,   # 500 × 220
        salary_max=132_000,   # 600 × 220
        salary_type="daily",
        description="Contract role: manage Azure landing zones and policy.",
        url="https://www.cwjobs.co.uk/job/azure-platform-engineer/87654321",
        source="CW Jobs",
        date_posted="2026-02-24T09:00:00Z",
        job_type="Contract",
    )


@pytest.fixture
def mock_unknown_salary_job():
    """A Job with no salary information (should still pass the filter)."""
    return Job(
        title="Azure DevOps Engineer",
        company="StartupXYZ",
        location="South East England",
        salary_raw="Not specified",
        salary_min=None,
        salary_max=None,
        salary_type="unknown",
        description="CI/CD pipelines on Azure DevOps, Docker, Kubernetes.",
        url="https://www.jobserve.com/gb/en/JobDetail/?j=ABC123",
        source="JobServe",
        date_posted="",
        job_type="",
    )


# ── Sample HTML fixtures for scraper unit tests ──────────────────────────────

REED_NEXT_DATA_TEMPLATE = """\
<html><head>
<script id="__NEXT_DATA__" type="application/json">{json_blob}</script>
</head><body></body></html>"""


@pytest.fixture
def sample_html_reed():
    """
    Minimal __NEXT_DATA__ HTML that mimics a Reed search results page.
    Contains one job that should pass all filters.
    """
    import json
    payload = {
        "props": {
            "pageProps": {
                "searchResults": {
                    "jobs": [
                        {
                            "jobDetail": {
                                "jobTitle": "Azure Cloud Engineer",
                                "dateCreated": "2026-02-26T08:00:00Z",
                                "salaryFrom": 65000,
                                "salaryTo": 80000,
                                "salaryType": 1,
                                "salaryDescription": "£65,000–£80,000 per annum",
                                "jobDescription": "<p>Build and maintain cloud infrastructure.</p>",
                                "displayLocationName": "London",
                                "ouName": "CloudCorp Ltd",
                                "jobType": 1,
                            },
                            "url": "/jobs/azure-cloud-engineer/99999999",
                        }
                    ]
                }
            }
        }
    }
    return REED_NEXT_DATA_TEMPLATE.format(json_blob=json.dumps(payload))


@pytest.fixture
def sample_html_reed_sc_cleared():
    """Reed HTML fixture for a job that must be excluded (SC cleared)."""
    import json
    payload = {
        "props": {
            "pageProps": {
                "searchResults": {
                    "jobs": [
                        {
                            "jobDetail": {
                                "jobTitle": "Azure Engineer - SC Cleared",
                                "dateCreated": "2026-02-26T08:00:00Z",
                                "salaryFrom": 70000,
                                "salaryTo": 90000,
                                "salaryType": 1,
                                "salaryDescription": "£70,000–£90,000 per annum",
                                "jobDescription": "<p>Must hold active SC clearance.</p>",
                                "displayLocationName": "London",
                                "ouName": "DefenceCorp",
                                "jobType": 1,
                            },
                            "url": "/jobs/azure-engineer-sc/11111111",
                        }
                    ]
                }
            }
        }
    }
    return REED_NEXT_DATA_TEMPLATE.format(json_blob=json.dumps(payload))


@pytest.fixture
def sample_html_cwjobs():
    """
    Minimal HTML that mimics a CW Jobs / Totaljobs page with the
    window.__PRELOADED_STATE__ assignment containing one Azure job.
    """
    import json
    items = [
        {
            "title": "Azure Network Engineer",
            "datePosted": "2026-02-25T12:00:00Z",
            "salary": "£60,000 - £75,000 per annum",
            "textSnippet": "Manage Azure networking components including VNets and ExpressRoute.",
            "location": "London",
            "companyName": "NetSolutions Ltd",
            "url": "/job/azure-network-engineer/54321",
        }
    ]
    state = {"searchResults": {"items": items}}
    state_json = json.dumps(state)
    return (
        "<html><head></head><body>"
        "<script>"
        f'window.__PRELOADED_STATE__["app-unifiedResultlist"] = {state_json};'
        "</script></body></html>"
    )
