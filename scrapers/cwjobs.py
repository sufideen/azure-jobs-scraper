"""
CW Jobs scraper (cwjobs.co.uk).
Job data is embedded in window.__PRELOADED_STATE__["app-unifiedResultlist"]
inside a <script> tag. Path: data["searchResults"]["items"].
"""
import json
import logging
import re

from utils.dates import parse_date, is_within_7_days
from utils.dedup import make_dedup_key
from utils.http import polite_get, delay
from utils.salary import parse_salary, salary_passes_filter

log = logging.getLogger(__name__)

BASE_URL = "https://www.cwjobs.co.uk"

SEARCH_TERMS = [
    "azure-infrastructure-engineer",
    "azure-platform-engineer",
    "azure-cloud-engineer",
    "azure-architect",
    "azure-devops-engineer",
    "azure-network-engineer",
    "azure-administrator",
    "azure-security-engineer",
]

SC_PHRASES = [
    "sc cleared", "sc clearance", "security cleared", "security clearance required",
    "dv cleared", "dv clearance", "active sc", "sc-cleared",
    "must hold sc", "require sc", "active dv",
]


def _build_url(term: str, base: str = BASE_URL) -> str:
    return (
        f"{base}/jobs/{term}"
        f"?location=London&distance=30&salary=50000&salarytype=annual&postedin=7"
    )


def _is_sc_cleared(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return any(p in text for p in SC_PHRASES)


def _extract_preloaded_state(html: str, source: str) -> list:
    """
    Extract items from the app-unifiedResultlist key of __PRELOADED_STATE__.

    CW Jobs and Totaljobs build up the state via individual property assignments:
        window.__PRELOADED_STATE__["app-unifiedResultlist"] = {...};
    We locate this specific assignment and parse only that JSON object.
    """
    pattern = r'window\.__PRELOADED_STATE__\[.app-unifiedResultlist.\]\s*=\s*(\{)'
    m = re.search(pattern, html)
    if not m:
        log.warning("%s: app-unifiedResultlist assignment not found in page", source)
        return []

    brace_start = m.start(1)
    depth = 0
    end = brace_start
    for i, ch in enumerate(html[brace_start:], brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        data = json.loads(html[brace_start:end])
    except json.JSONDecodeError as e:
        log.warning("%s: app-unifiedResultlist JSON parse failed: %s", source, e)
        return []

    items = data.get("searchResults", {}).get("items", [])
    if not items:
        log.warning("%s: no items in app-unifiedResultlist", source)
    return items


def extract_jobs_from_page(html: str, source: str = "CW Jobs", base_url: str = BASE_URL) -> list:
    """
    Parse a CW Jobs or Totaljobs page and return Job objects.
    Exported so totaljobs.py can reuse this with its own base_url.
    """
    from scraper import Job  # local import to avoid circular at module level

    items = _extract_preloaded_state(html, source)
    results = []

    for item in items:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        # Date filter
        date_str = parse_date(item.get("datePosted") or "")
        if not is_within_7_days(date_str):
            continue

        # Salary
        salary_raw = (item.get("salary") or "").strip()
        sal_min, sal_max, sal_type = parse_salary(salary_raw)
        if not salary_passes_filter(sal_min, sal_max):
            continue

        snippet = (item.get("textSnippet") or "").strip()

        # SC Cleared filter
        if _is_sc_cleared(title, snippet):
            continue

        location = (item.get("location") or "").strip()
        company = (item.get("companyName") or "").strip()
        url = (item.get("url") or "").strip()
        # Totaljobs returns relative URLs; prepend base_url when needed
        if url.startswith("/"):
            url = f"{base_url}{url}"

        job = Job(
            title=title,
            company=company,
            location=location,
            salary_raw=salary_raw or "Not specified",
            salary_min=sal_min,
            salary_max=sal_max,
            salary_type=sal_type,
            description=snippet[:600],
            url=url,
            source=source,
            date_posted=date_str,
            job_type="",
        )
        job.dedup_key = make_dedup_key(title, company, location)
        results.append(job)

    return results


def scrape_cwjobs() -> list:
    """Scrape CW Jobs for all Azure search terms. Returns list of Job objects."""
    all_jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS:
        url = _build_url(term)
        log.info("CW Jobs: fetching %s", url)
        resp = polite_get(url)
        if resp:
            jobs = extract_jobs_from_page(resp.text, "CW Jobs", BASE_URL)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        delay()

    log.info("CW Jobs total: %d jobs", len(all_jobs))
    return all_jobs
