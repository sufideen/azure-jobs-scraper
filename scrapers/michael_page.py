"""
Michael Page scraper (michaelpage.co.uk).
Parses server-rendered job tile HTML. Date extracted from JN reference in URL.

Notes:
- The ?keyword= parameter is not enforced server-side; MP returns all tech jobs.
  An Azure keyword post-filter is applied on title + description.
- JN references only have month-level date precision (jn-MMYYYY).
  We accept jobs from the current or previous month (approx. last 60 days)
  rather than 7 days, since intra-month postings all share the same JN prefix.
"""
import logging
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup

from utils.dates import parse_jn_date
from utils.dedup import make_dedup_key
from utils.http import polite_get, delay
from utils.salary import parse_salary, salary_passes_filter

log = logging.getLogger(__name__)

BASE_URL = "https://www.michaelpage.co.uk"

# Search URLs cover London city, broader London tech, and South East England
SEARCH_URLS = [
    f"{BASE_URL}/jobs/technology/london?keyword=Azure",
    f"{BASE_URL}/jobs/technology/city-london?keyword=Azure",
    f"{BASE_URL}/jobs/technology/south-east-england?keyword=Azure",
]

AZURE_KEYWORDS = [
    "azure infrastructure", "azure platform", "azure networking",
    "azure cloud", "azure architect", "azure devops", "azure network",
    "azure solutions", "azure administrator", "azure security",
    "azure engineer", "azure specialist", "azure consultant",
    "azure migration", "azure automation",
    # Broader matches — also catch "Azure Engineer", "Azure Specialist" in title alone
    " azure ",
]

SC_PHRASES = [
    "sc cleared", "sc clearance", "security cleared", "security clearance required",
    "dv cleared", "dv clearance", "active sc", "sc-cleared",
    "must hold sc", "require sc", "active dv",
]


def _is_azure_job(title: str, description: str) -> bool:
    # Pad with spaces so " azure " matches at word boundaries in title
    text = (" " + title + " " + description + " ").lower()
    return any(kw in text for kw in AZURE_KEYWORDS)


def _is_recent_jn(date_str: str) -> bool:
    """
    Accept jobs from the current or previous calendar month.
    JN references only have month-level precision (jn-MMYYYY), so we cannot
    filter to 7 days — we instead accept the last ~60 days.
    Returns True for unknown/missing dates.
    """
    if not date_str:
        return True
    try:
        from dateutil import parser as dp
        dt = dp.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=62)
        return dt >= cutoff
    except Exception:
        return True


def _is_sc_cleared(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(p in text for p in SC_PHRASES)


def _parse_tiles(html: str) -> list:
    from scraper import Job  # local import

    soup = BeautifulSoup(html, "lxml")
    tiles = soup.find_all("div", class_=lambda c: c and "job-tile" in c)
    results = []

    for tile in tiles:
        # Title and URL
        title_tag = tile.select_one("div.job-title h3 a") or tile.select_one("h3 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        full_url = f"{BASE_URL}{href}" if href.startswith("/") else href

        # Date from JN reference — month-level precision only; accept last 60 days
        date_str = parse_jn_date(href)
        if date_str and not _is_recent_jn(date_str):
            continue

        # Location
        loc_tag = tile.select_one("div.job-location") or tile.select_one("[class*='location']")
        location = loc_tag.get_text(strip=True) if loc_tag else "London"
        # Strip icon text (e.g. "location_on" from material icons)
        location = location.replace("location_on", "").strip()

        # Salary
        sal_tag = tile.select_one("div.job-salary") or tile.select_one("[class*='salary']")
        salary_raw = sal_tag.get_text(strip=True) if sal_tag else ""
        salary_raw = salary_raw.replace("attach_money", "").strip()
        sal_min, sal_max, sal_type = parse_salary(salary_raw)
        if not salary_passes_filter(sal_min, sal_max):
            continue

        # Job type
        type_tag = tile.select_one("div.job-contract-type") or tile.select_one("[class*='contract']")
        job_type = type_tag.get_text(strip=True) if type_tag else ""

        # Description
        desc_tag = (
            tile.select_one("div.job_advert__job-summary-text")
            or tile.select_one("[class*='summary']")
            or tile.select_one("p")
        )
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        # Azure keyword relevance check
        if not _is_azure_job(title, description):
            continue

        # SC Cleared filter
        if _is_sc_cleared(title, description):
            continue

        job = Job(
            title=title,
            company="Michael Page Client",
            location=location,
            salary_raw=salary_raw or "Not specified",
            salary_min=sal_min,
            salary_max=sal_max,
            salary_type=sal_type,
            description=description[:600],
            url=full_url,
            source="Michael Page",
            date_posted=date_str,
            job_type=job_type,
        )
        # Use "Michael Page" as company placeholder so dedup works across pages
        job.dedup_key = make_dedup_key(title, "Michael Page", location)
        results.append(job)

    return results


def scrape_michael_page() -> list:
    """Scrape Michael Page for Azure jobs in London & South East."""
    all_jobs = []
    seen_urls: set = set()

    for url in SEARCH_URLS:
        log.info("Michael Page: fetching %s", url)
        resp = polite_get(url)
        if resp:
            jobs = _parse_tiles(resp.text)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        delay(3, 7)

    log.info("Michael Page total: %d jobs", len(all_jobs))
    return all_jobs
