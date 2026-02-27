# Azure Jobs Scraper

[![CI](https://github.com/sufideen/azure-jobs-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/sufideen/azure-jobs-scraper/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/sufideen/azure-jobs-scraper/branch/main/graph/badge.svg)](https://codecov.io/gh/sufideen/azure-jobs-scraper)

A Python scraper that collects current **Azure infrastructure, platform, and networking jobs**
from five UK job boards, filters to London & South East / £50k+ / no SC-cleared roles,
and emails a styled HTML report twice daily.

Built as a **practical Python learning project** for intermediate developers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        scraper.py (main)                        │
│  Job dataclass · save_to_csv() · build_html_report() · SMTP     │
└───────────┬─────────────────────────────────────────────────────┘
            │ orchestrates
    ┌───────┴──────────────────────────────────────────┐
    │               scrapers/                          │
    │  reed.py     cwjobs.py    totaljobs.py           │
    │  (Next.js    (preloaded   (same structure        │
    │  __NEXT_DATA__  state JSON)  as cwjobs)          │
    │  JSON)                                           │
    │  michael_page.py    jobserve.py                  │
    │  (BeautifulSoup     (BeautifulSoup               │
    │  .job-tile HTML)    .sjJobItem HTML)             │
    └───────┬──────────────────────────────────────────┘
            │ uses
    ┌───────┴──────────────────────────────────────────┐
    │                   utils/                         │
    │  http.py      salary.py    dates.py   dedup.py  │
    │  (requests,   (regex,      (dateutil  (MD5       │
    │  UA rotation, k-expand,    7-day      fingerprint│
    │  back-off)    day rates)   filter)    dedup)     │
    └──────────────────────────────────────────────────┘
            │ outputs
    ┌───────┴──────────────────────────────────────────┐
    │   /home/sufideen/azure_jobs_YYYY-MM-DD_HH-MM.csv │
    │   /home/sufideen/azure_jobs_YYYY-MM-DD_HH-MM.html│
    │   Email → sufyan@ict-cloud.solutions (Gmail SMTP) │
    └──────────────────────────────────────────────────┘
```

---

## Python Concepts Covered

| Concept | File | Description |
|---------|------|-------------|
| `@dataclass` | `scraper.py` | Auto-generated `__init__`, `__repr__`, typed fields |
| `Optional[int]` | `scraper.py` | Type hint for nullable values |
| `fields()` introspection | `scraper.py` | Generate CSV headers dynamically from dataclass |
| Regex (`re`) | `utils/salary.py` | k-shorthand expansion, number extraction |
| `re.DOTALL` | `scrapers/reed.py` | Match `.` across newlines in multiline JSON |
| JSON extraction | `scrapers/reed.py` | Parse `__NEXT_DATA__` from Next.js SSR pages |
| Brace-counting | `scrapers/cwjobs.py` | Extract JSON from JS property assignments |
| BeautifulSoup | `scrapers/michael_page.py` | Parse server-rendered HTML job tiles |
| `python-dateutil` | `utils/dates.py` | Flexible date parsing, timezone-aware comparison |
| `hashlib.md5` | `utils/dedup.py` | Fingerprint deduplication across job boards |
| `requests` | `utils/http.py` | HTTP GET with rotating headers and back-off |
| `smtplib` + MIME | `scraper.py` | Gmail SMTP with HTML body and CSV attachment |
| `python-dotenv` | `scraper.py` | Credential management via `.env` file |
| `unittest.mock` | `tests/test_http.py` | Mock HTTP calls — no real network in tests |
| pytest fixtures | `tests/conftest.py` | Shared test data injected by name |
| `tmp_path` fixture | `tests/test_scraper.py` | Built-in pytest temp directory for file I/O tests |
| GitHub Actions | `.github/workflows/ci.yml` | Parallel lint, security, and test jobs |
| cron | system crontab | Twice-daily scheduled execution |

---

## Job Boards

| Board | Technique | Notes |
|-------|-----------|-------|
| Reed | `__NEXT_DATA__` JSON | Full salary, date, description |
| CW Jobs | `__PRELOADED_STATE__` JSON | Brace-counting extraction |
| Totaljobs | Same as CW Jobs | Relative URLs resolved to absolute |
| Michael Page | BeautifulSoup | JN refs → 60-day window; Azure post-filter |
| JobServe | BeautifulSoup | `?posted=7days` URL filter |

CV Library and Indeed UK return HTTP 403 (WAF-blocked) and are not included.

---

## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/sufideen/azure-jobs-scraper.git
cd azure-jobs-scraper
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure Gmail credentials

```bash
cp .env.example .env
# Edit .env and fill in GMAIL_USER and GMAIL_APP_PASSWORD
# Generate an App Password at: https://myaccount.google.com/apppasswords
```

### 3. Run

```bash
# Dry run — scrape and save files, skip email
venv/bin/python3 scraper.py --dry-run

# Full run — scrape, save, and send email
venv/bin/python3 scraper.py
```

Output files are saved to `/home/sufideen/azure_jobs_YYYY-MM-DD_HH-MM.{csv,html}`.

---

## Running Tests

```bash
# Install dev dependencies
venv/bin/pip install -r requirements-dev.txt

# Run all tests with coverage
venv/bin/pytest tests/ -v --cov=. --cov-report=term-missing

# Lint check
venv/bin/flake8 scraper.py scrapers/ utils/ --max-line-length=110

# Security scan
venv/bin/bandit -r scraper.py scrapers/ utils/ -ll
```

---

## Cron Schedule

The scraper runs at 08:00 and 18:00 every day via cron:

```
0  8 * * *  /path/to/venv/bin/python3 /path/to/scraper.py >> logs/cron.log 2>&1
0 18 * * *  /path/to/venv/bin/python3 /path/to/scraper.py >> logs/cron.log 2>&1
```

Edit with `crontab -e`. Use absolute paths — cron has a minimal `$PATH`.

---

## Project Structure

```
azure-jobs-scraper/
├── scraper.py              # Main orchestrator
├── scrapers/
│   ├── reed.py             # Reed.co.uk — Next.js JSON
│   ├── cwjobs.py           # CW Jobs — preloaded state JSON
│   ├── totaljobs.py        # Totaljobs — thin cwjobs wrapper
│   ├── michael_page.py     # Michael Page — BeautifulSoup
│   └── jobserve.py         # JobServe — BeautifulSoup
├── utils/
│   ├── http.py             # polite_get(), rotating User-Agents
│   ├── salary.py           # Salary parsing and filtering
│   ├── dates.py            # Date normalisation and recency
│   └── dedup.py            # MD5-based deduplication
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── test_salary.py
│   ├── test_dates.py
│   ├── test_dedup.py
│   ├── test_http.py
│   └── test_scraper.py
├── .github/workflows/
│   └── ci.yml              # GitHub Actions: lint + security + test
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Dev/test dependencies
├── pyproject.toml          # pytest, coverage, bandit config
├── .env.example            # Credential template (safe to commit)
├── LEARNING.md             # Annotated Python concept guide
└── .gitignore
```

---

## Filters Applied

- **Location:** London & South East (enforced at search URL level)
- **Salary:** £50,000+ per annum (day rates converted ×220 working days)
- **Recency:** Posted within last 7 days (60 days for Michael Page — JN refs are month-precision)
- **Exclusions:** SC Cleared, DV Cleared, security clearance required roles

---

## Learning Resource

See [LEARNING.md](LEARNING.md) for annotated deep-dives into every technique used,
including Next.js JSON extraction, brace-counting, BeautifulSoup, salary regex,
MD5 deduplication, anti-bot headers, Gmail SMTP, cron scheduling, `unittest.mock`,
and GitHub Actions CI.

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-change`
3. Run the test suite: `venv/bin/pytest tests/ -v`
4. Ensure lint passes: `venv/bin/flake8 scraper.py scrapers/ utils/ --max-line-length=110`
5. Open a pull request

---

## Disclaimer

This project scrapes publicly accessible job listings for personal use.
Always review a site's `robots.txt` and Terms of Service before scraping.
Polite delays are built in to avoid overloading servers.
