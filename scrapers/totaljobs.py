"""
Totaljobs scraper (totaljobs.com).
Shares the same page structure as CW Jobs — reuses the extractor from cwjobs.py.
"""
import logging

from scrapers.cwjobs import SEARCH_TERMS, extract_jobs_from_page
from utils.http import polite_get, delay

log = logging.getLogger(__name__)

BASE_URL = "https://www.totaljobs.com"


def _build_url(term: str) -> str:
    return (
        f"{BASE_URL}/jobs/{term}"
        f"?location=London&distance=30&salary=50000&salarytype=annual&postedin=7"
    )


def scrape_totaljobs() -> list:
    """Scrape Totaljobs for all Azure search terms. Returns list of Job objects."""
    all_jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS:
        url = _build_url(term)
        log.info("Totaljobs: fetching %s", url)
        resp = polite_get(url)
        if resp:
            jobs = extract_jobs_from_page(resp.text, "Totaljobs", BASE_URL)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        delay()

    log.info("Totaljobs total: %d jobs", len(all_jobs))
    return all_jobs
