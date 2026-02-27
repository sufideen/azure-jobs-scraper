"""
Reed.co.uk scraper.
Extracts job data from the __NEXT_DATA__ JSON embedded in each search page.
"""
import json
import logging
import re

from bs4 import BeautifulSoup

from utils.dates import parse_date, is_within_7_days
from utils.dedup import make_dedup_key
from utils.http import polite_get, delay
from utils.salary import salary_passes_filter

log = logging.getLogger(__name__)

BASE_URL = "https://www.reed.co.uk"
SALARY_FILTER = 50_000

# Reed URL search slugs — all scoped to London
SEARCH_SLUGS = [
    "azure-infrastructure",
    "azure-platform",
    "azure-networking",
    "azure-cloud-engineer",
    "azure-architect",
    "azure-devops-engineer",
    "azure-network-engineer",
    "azure-solutions-engineer",
    "azure-administrator",
    "azure-security-engineer",
]

SC_PHRASES = [
    "sc cleared", "sc clearance", "security cleared", "security clearance required",
    "dv cleared", "dv clearance", "active sc", "sc-cleared", "sc level",
    "must hold sc", "require sc", "active dv", "nsc cleared", "bpss cleared",
]


def _build_url(slug: str) -> str:
    return f"{BASE_URL}/jobs/{slug}-jobs-in-london?salaryFrom={SALARY_FILTER}"


def _is_sc_cleared(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(phrase in text for phrase in SC_PHRASES)


def _reed_salary_type(type_id: int) -> str:
    return {1: "annual", 2: "daily"}.get(type_id, "annual")


def _reed_job_type(type_id: int) -> str:
    return {1: "Permanent", 2: "Contract", 3: "Temporary"}.get(type_id, "")


def _extract_jobs(html: str) -> list:
    """Parse Reed __NEXT_DATA__ JSON and return a list of Job dicts."""
    from scraper import Job  # local import to avoid circular dependency at module load

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        log.warning("Reed: __NEXT_DATA__ not found in page")
        return []

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        log.warning("Reed: JSON parse failed: %s", e)
        return []

    jobs_raw = (
        data.get("props", {})
            .get("pageProps", {})
            .get("searchResults", {})
            .get("jobs", [])
    )

    results = []
    for item in jobs_raw:
        jd = item.get("jobDetail", {})

        title = (jd.get("jobTitle") or "").strip()
        if not title:
            continue

        # Date filter
        date_str = parse_date(jd.get("dateCreated", ""))
        if not is_within_7_days(date_str):
            continue

        # Salary — Reed provides structured numeric values
        sal_from = jd.get("salaryFrom") or 0
        sal_to = jd.get("salaryTo") or 0
        sal_type_id = jd.get("salaryType") or 1
        sal_type = _reed_salary_type(sal_type_id)
        # salaryDescription can be int (0) in some Reed responses — coerce to str safely
        sal_desc_raw = jd.get("salaryDescription")
        sal_desc = str(sal_desc_raw).strip() if sal_desc_raw else ""

        if sal_from > 0:
            if sal_type == "daily":
                sal_min = int(sal_from) * 220
                sal_max = int(sal_to) * 220 if sal_to else sal_min
                sal_display = (
                    f"£{int(sal_from)}–£{int(sal_to)}/day"
                    if sal_to else f"£{int(sal_from)}/day"
                )
            else:
                sal_min = int(sal_from)
                sal_max = int(sal_to) if sal_to else sal_min
                sal_display = sal_desc or f"£{sal_min:,}–£{sal_max:,}"
        else:
            sal_min, sal_max, sal_type = None, None, "unknown"
            sal_display = sal_desc or "Not specified"

        if not salary_passes_filter(sal_min, sal_max):
            continue

        # Description — strip HTML
        raw_desc = jd.get("jobDescription") or ""
        description = BeautifulSoup(raw_desc, "lxml").get_text(" ", strip=True)

        # SC Cleared filter
        if _is_sc_cleared(title, description):
            continue

        location = (jd.get("displayLocationName") or "").strip()
        company = (jd.get("ouName") or "").strip()
        url_path = item.get("url") or ""
        full_url = (
            f"{BASE_URL}{url_path}" if url_path.startswith("/") else url_path
        )
        job_type = _reed_job_type(jd.get("jobType") or 0)

        job = Job(
            title=title,
            company=company,
            location=location,
            salary_raw=sal_display,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_type=sal_type,
            description=description[:600],
            url=full_url,
            source="Reed",
            date_posted=date_str,
            job_type=job_type,
        )
        job.dedup_key = make_dedup_key(title, company, location)
        results.append(job)

    return results


def scrape_reed() -> list:
    """Scrape Reed for all Azure search slugs. Returns list of Job objects."""
    all_jobs = []
    seen_urls: set = set()

    for slug in SEARCH_SLUGS:
        url = _build_url(slug)
        log.info("Reed: fetching %s", url)
        resp = polite_get(url)
        if not resp:
            log.warning("Reed: no response for slug '%s'", slug)
            delay(3, 6)
            continue

        jobs = _extract_jobs(resp.text)
        new_count = 0
        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)
                new_count += 1

        log.info("Reed [%s]: %d new jobs (page total: %d)", slug, new_count, len(jobs))
        delay(3, 6)

    log.info("Reed total: %d jobs", len(all_jobs))
    return all_jobs
