"""Temporary debug script: dump the raw jobDetail keys Reed actually returns.
Run with: venv/bin/python3 debug_reed_fields.py
Delete this file once the real field name is confirmed.
"""
import json
import re

from utils.http import polite_get

url = "https://www.reed.co.uk/jobs/azure-infrastructure-jobs-in-london?salaryFrom=50000"
resp = polite_get(url)
if not resp:
    print("No response from Reed.")
    raise SystemExit(1)

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
if not m:
    print("__NEXT_DATA__ not found.")
    raise SystemExit(1)

data = json.loads(m.group(1))
jobs = data.get("props", {}).get("pageProps", {}).get("searchResults", {}).get("jobs", [])
print(f"Found {len(jobs)} jobs.\n")

if jobs:
    jd = jobs[0].get("jobDetail", {})
    print("Keys in jobDetail:", sorted(jd.keys()))
    print()
    print("Full jobDetail for first job:")
    print(json.dumps(jd, indent=2)[:3000])
    print()

print("Salary fields across all jobs on this page (checking for the")
print("£550,000 / bare-number display bugs seen in the real CSV):")
for item in jobs:
    jd = item.get("jobDetail", {})
    print({
        "title": jd.get("jobTitle"),
        "salaryFrom": jd.get("salaryFrom"),
        "salaryTo": jd.get("salaryTo"),
        "salaryType": jd.get("salaryType"),
        "salaryDescription": jd.get("salaryDescription"),
        "hasJobDescription": bool(jd.get("jobDescription")),
        "jobDescriptionLen": len(jd.get("jobDescription") or ""),
    })
