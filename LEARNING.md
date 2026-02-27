# Python Learning Guide — Azure Jobs Scraper

This document explains the intermediate Python concepts used in this project.
Each section links the concept to the file where you can find it in action.

---

## 1. Dataclasses (`scraper.py`)

Python `@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__` from
field declarations. The `field(default="")` syntax provides a mutable default
without the usual Python gotcha.

```python
from dataclasses import dataclass, field, fields
from typing import Optional

@dataclass
class Job:
    title: str
    salary_min: Optional[int]   # can be int or None
    dedup_key: str = field(default="")  # mutable default — safe with field()
```

**Why not a plain dict?** Dataclasses give you dot-access (`job.title`),
type annotations for IDE support, and make the shape of your data explicit.

**Key concept — `fields(Job)`:** The `fields()` function introspects the
dataclass at runtime, letting us generate `CSV_FIELDNAMES` automatically
instead of hard-coding the column list.

---

## 2. Extracting Embedded JSON from Next.js Pages (`scrapers/reed.py`)

Modern sites built with Next.js (React SSR) embed their full page data as JSON
inside a `<script id="__NEXT_DATA__">` tag. This is server-rendered HTML
containing structured data — no JavaScript execution needed.

```python
import json, re

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
data = json.loads(m.group(1))

# Navigate the nested dict:
jobs = data["props"]["pageProps"]["searchResults"]["jobs"]
```

**`re.DOTALL`** makes `.` match newline characters — essential when the JSON
blob spans multiple lines. Without it, `.*?` stops at the first `\n`.

**Path:** `scrapers/reed.py:_extract_jobs()`

---

## 3. Brace-Counting JSON Extraction (`scrapers/cwjobs.py`)

Some sites don't embed one clean JSON blob. Instead they build up a global
state object with individual property assignments:

```javascript
window.__PRELOADED_STATE__["app-unifiedResultlist"] = {"searchResults": ...};
window.__PRELOADED_STATE__["app-header"] = {...};
```

We can't just `json.loads()` the whole script. Instead:
1. Use regex to find the `=` for our target key.
2. Walk character-by-character counting `{` and `}` to find the matching
   closing brace.
3. Slice out and parse only that JSON object.

```python
pattern = r'window\.__PRELOADED_STATE__\[.app-unifiedResultlist.\]\s*=\s*(\{)'
m = re.search(pattern, html)
brace_start = m.start(1)
depth = 0
for i, ch in enumerate(html[brace_start:], brace_start):
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
data = json.loads(html[brace_start:end])
```

**Why not Beautiful Soup?** BeautifulSoup parses HTML structure, not arbitrary
JavaScript values. For embedded data, regex + brace-counting is more reliable.

**Path:** `scrapers/cwjobs.py:_extract_preloaded_state()`

---

## 4. BeautifulSoup HTML Parsing (`scrapers/michael_page.py`, `scrapers/jobserve.py`)

When sites render job tiles as server-side HTML (not embedded JSON), we use
BeautifulSoup to navigate the DOM tree.

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "lxml")

# Select by CSS class (partial match with lambda):
tiles = soup.find_all("div", class_=lambda c: c and "job-tile" in c)

# CSS selector syntax:
title_tag = tile.select_one("div.job-title h3 a")
title = title_tag.get_text(strip=True)

# Fallback chaining with `or`:
loc_tag = tile.select_one("div.job-location") or tile.select_one("[class*='location']")
```

**`lxml` parser** is faster than Python's built-in `html.parser` and more
lenient with malformed HTML — important for real-world sites.

**Path:** `scrapers/michael_page.py:_parse_tiles()`

---

## 5. Salary Parsing with Regex (`utils/salary.py`)

Real salary strings are messy:
- `"£60,000 - £80,000 per annum"` — range with currency and period
- `"60k - 80k"` — k-shorthand
- `"£450 - £550 per day"` — daily rate
- `"Competitive salary"` — unparseable

Strategy:
1. Lowercase + strip commas and `£` signs
2. Detect daily/annual from keyword presence
3. Expand `k` shorthand with regex substitution
4. Extract all numbers ≥ 100 (ignores band/grade numbers)
5. Apply heuristic: values < 2000 without annual keyword = daily rate

```python
# Expand "60k" → "60000"
normalised = re.sub(
    r'(\d+(?:\.\d+)?)\s*k\b',          # match "60k", "60.5k"
    lambda m: str(int(float(m.group(1)) * 1000)),
    text,
)

# Extract numbers as integers
nums = re.findall(r'\d+(?:\.\d+)?', normalised)
nums = [int(float(n)) for n in nums if int(float(n)) >= 100]
```

**`(?:\.\d+)?`** — non-capturing group (`?:`) for an optional decimal part.
Non-capturing groups are faster than capturing groups when you don't need the
matched text.

**Path:** `utils/salary.py:parse_salary()`

---

## 6. MD5 Deduplication (`utils/dedup.py`)

Jobs often appear on multiple boards simultaneously. We detect duplicates by
hashing a normalised `(title, company, location)` fingerprint.

```python
import hashlib, re

def _normalise(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)   # remove punctuation
    s = re.sub(r'\s+', ' ', s).strip()   # collapse whitespace
    return s

def make_dedup_key(title, company, location):
    key = f"{_normalise(title)}|{_normalise(company)}|{_normalise(location)}"
    return hashlib.md5(key.encode()).hexdigest()
```

**Why MD5?** It's fast and produces a compact 32-char hex string. Security is
irrelevant here — we're fingerprinting text, not protecting passwords. Bandit
(security linter) flags MD5 with B324; we suppress it in `pyproject.toml`
with `skips = ["B324"]`.

**Collision resolution rule:** prefer known salary → prefer longer description.

**Path:** `utils/dedup.py`

---

## 7. Anti-Bot Measures (`utils/http.py`)

Scraping websites that don't want to be scraped requires mimicking a real browser:

```python
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    # ...
]

def get_headers(extra=None):
    return {
        "User-Agent": random.choice(USER_AGENTS),   # rotate per request
        "Accept-Encoding": "gzip, deflate",          # NOT "br" — see below
        "DNT": "1",                                  # Do Not Track header
        ...
    }
```

**Brotli gotcha:** Many modern sites advertise Brotli (`br`) compression.
If `requests` sends `Accept-Encoding: br`, the server compresses the response
with Brotli, but `requests` can't decompress it — you get garbled binary.
Fix: explicitly exclude `br` from the header.

**Polite delays:** `time.sleep(random.uniform(2, 5))` between requests avoids
triggering rate-limiters and is courteous to site servers.

**Back-off on 429:** When a server returns HTTP 429 (Too Many Requests) or 403
(Forbidden), we sleep progressively longer before retrying.

**Path:** `utils/http.py`

---

## 8. Gmail SMTP Email (`scraper.py`)

Python's standard library includes `smtplib` for sending email. Gmail requires
an **App Password** (a 16-character code) — not your regular login password —
when 2-Step Verification is enabled.

```python
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

msg = MIMEMultipart("mixed")
msg["Subject"] = "Azure Jobs Report"
msg["From"] = gmail_user
msg["To"] = recipient

msg.attach(MIMEText(html_body, "html", "utf-8"))    # HTML body
msg.attach(csv_attachment)                           # CSV file

context = ssl.create_default_context()              # verifies server certificate
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(gmail_user, app_password)
    server.sendmail(gmail_user, recipient, msg.as_string())
```

**Port 465 (SSL)** vs **Port 587 (STARTTLS):** Port 465 wraps the entire
connection in SSL from the start. Port 587 starts unencrypted then upgrades.
Both are secure; port 465 is simpler.

**CSV attachment:** The file is read as bytes, base64-encoded by
`encoders.encode_base64()`, and attached as `application/octet-stream`.

**Path:** `scraper.py:send_email_report()`

---

## 9. Cron Scheduling (System Cron)

The scraper runs automatically via `cron`, the Unix task scheduler. Cron reads
a **crontab** file with one job per line:

```
# m  h  dom  mon  dow  command
  0  8  *    *    *    /path/to/venv/bin/python3 /path/to/scraper.py >> logs/cron.log 2>&1
  0  18 *    *    *    /path/to/venv/bin/python3 /path/to/scraper.py >> logs/cron.log 2>&1
```

- `0 8 * * *` — at minute 0, hour 8, every day
- `2>&1` — redirects stderr to stdout so both go into the log file
- **Absolute paths everywhere** — cron has a minimal `$PATH`; relative paths fail silently

**`venv/bin/python3`** — using the virtualenv Python ensures the right
package versions are used, not the system Python.

**Edit crontab:** `crontab -e` — opens in your default editor.

---

## 10. Testing with `unittest.mock` (`tests/test_http.py`)

Tests that make real HTTP requests are slow, fragile, and rude to websites.
`unittest.mock.patch` replaces a function with a `MagicMock` for the duration
of the test.

```python
from unittest.mock import MagicMock, patch

@patch("utils.http.requests.get")   # ← patch WHERE IT'S USED, not where defined
def test_successful_get(self, mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = polite_get("https://example.com")

    assert result is mock_resp
    mock_get.assert_called_once()  # verify the function was called
```

**Critical:** Patch `"utils.http.requests.get"` — the name as imported in
`utils/http.py` — not `"requests.get"`. Python mocking works on the object in
the module's namespace, not the original definition.

**`MagicMock`** automatically creates attributes and methods on access.
`mock_resp.raise_for_status.return_value = None` means calling
`resp.raise_for_status()` does nothing (no exception raised).

**Path:** `tests/test_http.py`

---

## 11. pytest Fixtures (`tests/conftest.py`)

Fixtures provide reusable test data and setup, injected by name into test
functions. `conftest.py` is automatically discovered by pytest in the
current and parent directories.

```python
# conftest.py
@pytest.fixture
def mock_job():
    return Job(title="Azure Engineer", ...)

# test_scraper.py
def test_csv_data_row(mock_job):       # pytest injects the fixture
    save_to_csv([mock_job], "test.csv")
    # ... assertions
```

**`tmp_path`** is a built-in pytest fixture that provides a temporary directory
unique to each test — perfect for testing file I/O without polluting your
working directory.

**Fixture scope:** By default, fixtures run once per test function. Use
`@pytest.fixture(scope="module")` to share expensive setup across a module.

---

## 12. GitHub Actions CI (`/.github/workflows/ci.yml`)

The CI pipeline runs automatically on every push and pull request. It has
three parallel jobs:

```yaml
jobs:
  lint:
    steps:
      - run: flake8 scraper.py scrapers/ utils/ --max-line-length=110

  security:
    steps:
      - run: bandit -r scraper.py scrapers/ utils/ -ll

  test:
    steps:
      - run: pytest tests/ --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v4  # uploads coverage.xml to Codecov
```

**Why 3 jobs instead of 3 steps?** Parallel jobs run simultaneously on
separate GitHub-hosted VMs, making the CI faster. If lint fails, security
and tests still run independently.

**`-ll` (bandit):** Only report medium and high severity issues. `-l` is low+,
`-ll` is medium+.

**`--max-line-length=110`:** PEP 8 recommends 79 characters; many teams
use 100–120 for modern screens. The HTML template strings in this project
have long inline CSS — 110 is a pragmatic compromise.

---

## 13. python-dotenv and Credential Management

Hard-coding secrets in source code is a serious security risk. `python-dotenv`
reads key=value pairs from a `.env` file into `os.environ`:

```python
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

gmail_user = os.getenv("GMAIL_USER", "").strip()
```

**`.gitignore`** prevents `.env` from being committed. The `.env.example`
file (which IS committed) shows the required variable names with placeholder
values — safe to share publicly.

**`os.getenv("KEY", default)`** returns `default` if the variable is missing,
avoiding `KeyError` when running tests without a `.env` file.

---

## Further Reading

| Topic | Python Docs |
|-------|------------|
| Dataclasses | [docs.python.org/3/library/dataclasses.html](https://docs.python.org/3/library/dataclasses.html) |
| `re` module | [docs.python.org/3/library/re.html](https://docs.python.org/3/library/re.html) |
| `unittest.mock` | [docs.python.org/3/library/unittest.mock.html](https://docs.python.org/3/library/unittest.mock.html) |
| `smtplib` | [docs.python.org/3/library/smtplib.html](https://docs.python.org/3/library/smtplib.html) |
| BeautifulSoup | [beautiful-soup-4.readthedocs.io](https://beautiful-soup-4.readthedocs.io/) |
| pytest | [docs.pytest.org](https://docs.pytest.org/) |
| GitHub Actions | [docs.github.com/en/actions](https://docs.github.com/en/actions) |
