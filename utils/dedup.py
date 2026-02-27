"""
Job deduplication using MD5 fingerprint of normalised (title, company, location).
"""
import hashlib
import re


def _normalise(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def make_dedup_key(title: str, company: str, location: str) -> str:
    """MD5 fingerprint of normalised title|company|location."""
    key = f"{_normalise(title)}|{_normalise(company)}|{_normalise(location)}"
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate_jobs(jobs: list) -> list:
    """
    Remove duplicate jobs that appear on multiple boards.
    On collision, prefer the version with:
      1. Known salary (salary_min is not None)
      2. Longer description (more information)
    """
    seen: dict = {}
    for job in jobs:
        key = job.dedup_key
        if key not in seen:
            seen[key] = job
        else:
            existing = seen[key]
            existing_has_salary = existing.salary_min is not None
            new_has_salary = job.salary_min is not None
            if new_has_salary and not existing_has_salary:
                seen[key] = job
            elif new_has_salary == existing_has_salary:
                if len(job.description) > len(existing.description):
                    seen[key] = job
    return list(seen.values())
