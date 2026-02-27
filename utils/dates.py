"""
Date utilities: normalise to ISO 8601, 7-day recency check,
and Michael Page JN-reference date extraction.
"""
import re
from datetime import datetime, timezone, timedelta

from dateutil import parser as dateparser


def parse_date(raw: str) -> str:
    """Normalise any date string to ISO 8601 UTC. Returns raw on failure."""
    if not raw or not raw.strip():
        return ""
    try:
        dt = dateparser.parse(raw)
        if dt is None:
            return raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return raw


def is_within_7_days(date_str: str) -> bool:
    """
    Return True if the date is within the last 7 days.
    Unknown / unparseable dates return True (include by default).
    """
    if not date_str:
        return True
    try:
        dt = dateparser.parse(date_str)
        if dt is None:
            return True
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        return dt >= cutoff
    except Exception:
        return True


def parse_jn_date(jn_ref: str) -> str:
    """
    Extract a posting date from a Michael Page JN reference URL segment.

    Example: '/jobs/it-technology/london/jn-022026-6946427/azure-engineer'
             → month=02, year=2026 → '2026-02-01T00:00:00Z'
    """
    m = re.search(r'jn-(\d{2})(\d{4})-', jn_ref, re.IGNORECASE)
    if m:
        month, year = m.group(1), m.group(2)
        return f"{year}-{month}-01T00:00:00Z"
    return ""
