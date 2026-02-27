"""
Salary parsing utilities.
Handles annual and daily rate formats from all 5 job boards.
"""
import re
from typing import Optional, Tuple

# Conservative UK contractor working days assumption
WORKING_DAYS_PER_YEAR = 220


def parse_salary(raw: str) -> Tuple[Optional[int], Optional[int], str]:
    """
    Parse a salary string into (annual_min, annual_max, salary_type).

    salary_type: "annual" | "daily" | "unknown"
    Day rates are converted to annual equivalents (× WORKING_DAYS_PER_YEAR)
    so that the £50k threshold filter works consistently.

    Returns (None, None, "unknown") when salary cannot be determined.
    """
    if not raw or not raw.strip():
        return None, None, "unknown"

    text = raw.lower().replace(",", "").replace("£", "")

    # Detect rate type from keywords
    is_daily = any(t in text for t in [
        "per day", "/day", "p/d", " pd", "daily", "p.d.", "per diem", "day rate",
    ])
    is_annual = any(t in text for t in [
        "per annum", "per year", "/yr", " pa", "annually", "a year", "per yr",
    ])

    # Expand "k" shorthand: "60k" → "60000", "£480k" already stripped of £
    normalised = re.sub(
        r'(\d+(?:\.\d+)?)\s*k\b',
        lambda m: str(int(float(m.group(1)) * 1000)),
        text,
    )

    # Extract all numeric values (ignore percentages, days < 100, noise)
    nums = re.findall(r'\d+(?:\.\d+)?', normalised)
    nums = [int(float(n)) for n in nums if int(float(n)) >= 100]

    if not nums:
        return None, None, "unknown"

    sal_min = nums[0]
    sal_max = nums[1] if len(nums) > 1 else nums[0]

    if sal_min > sal_max:
        sal_min, sal_max = sal_max, sal_min

    # Heuristic: values < 2000 that are not explicitly annual are day rates
    if is_daily or (not is_annual and sal_max < 2000):
        return sal_min * WORKING_DAYS_PER_YEAR, sal_max * WORKING_DAYS_PER_YEAR, "daily"

    return sal_min, sal_max, "annual"


def salary_passes_filter(
    sal_min: Optional[int],
    sal_max: Optional[int],
    threshold: int = 50_000,
) -> bool:
    """
    Return True if the job's salary meets the threshold.
    Jobs with unknown salary (None) are included by default.
    """
    if sal_min is None and sal_max is None:
        return True  # unknown salary — give benefit of doubt
    effective = sal_max if sal_max is not None else sal_min
    return effective >= threshold


def format_salary_display(
    sal_min: Optional[int],
    sal_max: Optional[int],
    sal_type: str,
    raw: str,
) -> str:
    """Human-readable salary string for report display. Falls back to raw."""
    if sal_min is None:
        return raw or "Not specified"
    if sal_type == "daily":
        day_min = sal_min // WORKING_DAYS_PER_YEAR
        day_max = sal_max // WORKING_DAYS_PER_YEAR if sal_max else day_min
        if day_min == day_max:
            return f"£{day_min}/day"
        return f"£{day_min}–£{day_max}/day"
    if sal_min == sal_max:
        return f"£{sal_min:,}"
    return f"£{sal_min:,}–£{sal_max:,}"
