"""
HTTP utilities: polite_get() with rotating User-Agents and random delays.
"""
import logging
import random
import time

import requests

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 18

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def get_headers(extra: dict = None) -> dict:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        # Exclude 'br' (Brotli) — requests cannot decompress it natively,
        # which causes garbled responses from sites like CW Jobs and Totaljobs.
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


def polite_get(url: str, extra_headers: dict = None, retries: int = 2) -> requests.Response | None:
    """HTTP GET with rotating User-Agent, timeout, retries, and back-off on 429/403."""
    if not url:
        return None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url,
                headers=get_headers(extra_headers),
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            log.warning("HTTP %s for %s (attempt %d/%d)", status, url, attempt + 1, retries + 1)
            if status in (403, 429):
                time.sleep(10 * (attempt + 1))
        except requests.exceptions.Timeout:
            log.warning("Timeout: %s (attempt %d/%d)", url, attempt + 1, retries + 1)
        except requests.exceptions.RequestException as e:
            log.warning("Network error for %s: %s", url, e)
    return None


def delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Random polite delay between requests."""
    time.sleep(random.uniform(min_s, max_s))
