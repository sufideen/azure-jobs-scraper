"""
JobServe scraper (jobserve.com).
Parses server-rendered job listing HTML. Uses ?posted=7days URL filter.
Replaces CV Library and Indeed UK which both return 403 (WAF-blocked).
"""
import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from utils.dates import parse_date, is_within_7_days
from utils.dedup import make_dedup_key
from utils.http import polite_get, delay
from utils.salary import parse_salary, salary_passes_filter

log = logging.getLogger(__name__)

BASE_URL = "https://www.jobserve.com"

SEARCH_TERMS = [
    "azure infrastructure",
    "azure platform",
    "azure cloud engineer",
    "azure architect",
    "azure devops engineer",
    "azure network engineer",
    "azure administrator",
    "azure security engineer",
]

SC_PHRASES = [
    "sc cleared", "sc clearance", "security cleared", "security clearance required",
    "dv cleared", "dv clearance", "active sc", "sc-cleared",
    "must hold sc", "require sc", "active dv",
]


def _build_url(term: str) -> str:
    slug = term.replace(" ", "+")
    return f"{BASE_URL}/gb/en/job-search/?shid={slug}&l=London&radius=30&posted=7days"


def _parse_jobserve_date(raw: str) -> str:
    """Parse JobServe date format: '2/27/2026 11:38:00 AM'"""
    try:
        dt = datetime.strptime(raw.strip(), "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return parse_date(raw)


def _is_sc_cleared(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(p in text for p in SC_PHRASES)


def _parse_page(html: str) -> list:
    from scraper import Job  # local import

    soup = BeautifulSoup(html, "lxml")
    items = soup.find_all("div", class_="sjJobItem")
    results = []

    for item in items:
        # Title + URL
        title_tag = item.select_one("h3.sjJobTitle a.sjJobLink") or item.select_one("h3 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        full_url = f"{BASE_URL}{href}" if href.startswith("/") else href

        # Location + Salary — typically "London - £60,000 - £80,000 per annum"
        loc_sal_tag = item.select_one("p.sjJobLocationSalary") or item.select_one("[class*='LocationSalary']")
        loc_sal_text = loc_sal_tag.get_text(strip=True) if loc_sal_tag else ""

        # Split on " - " to separate location from salary
        parts = loc_sal_text.split(" - ", 1)
        location = parts[0].strip() if parts else "London"
        salary_raw = parts[1].strip() if len(parts) > 1 else ""

        sal_min, sal_max, sal_type = parse_salary(salary_raw)
        if not salary_passes_filter(sal_min, sal_max):
            continue

        # Date — may have class "none sjJobPosted" (hidden) so match loosely
        date_tag = item.find("p", class_=re.compile(r"\bsjJobPosted\b"))
        date_str = _parse_jobserve_date(date_tag.get_text(strip=True)) if date_tag else ""
        if not is_within_7_days(date_str):
            continue

        # Description
        desc_tag = item.select_one("p.sjJobDesc") or item.select_one("[class*='Desc']")
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        # Job type
        type_tag = item.select_one("p.sjJobType") or item.select_one("[class*='JobType']")
        job_type = type_tag.get_text(strip=True) if type_tag else ""

        # Company (not always present)
        co_tag = item.select_one("p.sjRecruiterName") or item.select_one("[class*='Recruiter']")
        company = co_tag.get_text(strip=True) if co_tag else ""

        # SC Cleared filter
        if _is_sc_cleared(title, description):
            continue

        job = Job(
            title=title,
            company=company,
            location=location,
            salary_raw=salary_raw or "Not specified",
            salary_min=sal_min,
            salary_max=sal_max,
            salary_type=sal_type,
            description=description[:600],
            url=full_url,
            source="JobServe",
            date_posted=date_str,
            job_type=job_type,
        )
        job.dedup_key = make_dedup_key(title, company, location)
        results.append(job)

    return results


def scrape_jobserve() -> list:
    """Scrape JobServe for all Azure search terms. Returns list of Job objects."""
    all_jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS:
        url = _build_url(term)
        log.info("JobServe: fetching %s", url)
        resp = polite_get(url)
        if resp:
            jobs = _parse_page(resp.text)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        delay()

    log.info("JobServe total: %d jobs", len(all_jobs))
    return all_jobs
