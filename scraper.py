#!/usr/bin/env python3
"""
Azure Jobs Scraper
==================
Scrapes Reed, CW Jobs, Totaljobs, Michael Page, and JobServe for current
Azure infrastructure, platform, and networking jobs in London & South East.

Filters:
  - Posted within the last 7 days
  - Salary >= £50,000 (day rates converted to annual equivalent)
  - Excludes SC/DV Cleared roles
  - Location: London & South East (enforced at search-URL level)

Outputs:
  - /home/sufideen/azure_jobs_YYYY-MM-DD_HH-MM.csv
  - /home/sufideen/azure_jobs_YYYY-MM-DD_HH-MM.html
  - HTML report emailed to RECIPIENT_EMAIL via Gmail SMTP

Usage:
  python3 scraper.py              # full run (scrape + save + email)
  python3 scraper.py --dry-run    # scrape + save, skip email
"""

import argparse
import csv
import logging
import os
import smtplib
import ssl
import sys
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

LONDON_TZ = ZoneInfo("Europe/London")
OUTPUT_DIR = Path("/home/sufideen")

# ── Data Model ────────────────────────────────────────────────────────────────


@dataclass
class Job:
    title: str
    company: str
    location: str
    salary_raw: str          # display string e.g. "£60,000–£80,000 per annum"
    salary_min: Optional[int]  # annual equivalent in £
    salary_max: Optional[int]
    salary_type: str         # "annual" | "daily" | "unknown"
    description: str         # first 600 chars
    url: str
    source: str              # "Reed" | "CW Jobs" | "Totaljobs" | "Michael Page" | "JobServe"
    date_posted: str         # ISO 8601
    job_type: str            # "Permanent" | "Contract" | ""
    dedup_key: str = field(default="")


CSV_FIELDNAMES = [f.name for f in fields(Job) if f.name != "dedup_key"]

# ── CSV Export ────────────────────────────────────────────────────────────────


def save_to_csv(jobs: list, filepath: str) -> None:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_raw": job.salary_raw,
                "salary_min": job.salary_min if job.salary_min is not None else "",
                "salary_max": job.salary_max if job.salary_max is not None else "",
                "salary_type": job.salary_type,
                "description": job.description,
                "url": job.url,
                "source": job.source,
                "date_posted": job.date_posted,
                "job_type": job.job_type,
            })
    log.info("CSV saved: %s (%d jobs)", filepath, len(jobs))

# ── HTML Report ───────────────────────────────────────────────────────────────


def build_html_report(jobs: list, session_label: str = "") -> str:
    """
    Build a Gmail-safe inline-CSS HTML report.
    Jobs sorted by salary descending.
    Salary colour-coded: green >= £80k, amber £50k–£79k, grey unknown.
    """
    generated_at = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    label_text = f" \u2014 {session_label}" if session_label else ""

    sorted_jobs = sorted(jobs, key=lambda j: (j.salary_max or 0), reverse=True)

    rows_html = ""
    for i, job in enumerate(sorted_jobs):
        bg = "#ffffff" if i % 2 == 0 else "#f7f9fc"
        sal_val = job.salary_max or job.salary_min or 0
        if sal_val >= 80_000:
            sal_colour = "#1a7340"
        elif sal_val >= 50_000:
            sal_colour = "#8a6500"
        else:
            sal_colour = "#666666"

        desc_short = (
            job.description[:200] + "..." if len(job.description) > 200 else job.description
        )
        # Escape any stray HTML in description
        desc_safe = (
            desc_short
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        title_safe = job.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        company_safe = (job.company or "\u2014").replace("&", "&amp;")
        location_safe = (job.location or "\u2014").replace("&", "&amp;")
        job_type_safe = (job.job_type or "").replace("&", "&amp;")

        rows_html += f"""
    <tr>
      <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;background:{bg};
                 vertical-align:top;width:22%;">
        <a href="{job.url}" style="color:#0078D4;text-decoration:none;font-weight:600;
                                   font-size:13px;line-height:1.4;" target="_blank">
          {title_safe}
        </a>
        <div style="font-size:11px;color:#888;margin-top:3px;">{job.source}</div>
      </td>
      <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;background:{bg};
                 vertical-align:top;width:17%;font-size:12px;color:#333;">
        {company_safe}
      </td>
      <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;background:{bg};
                 vertical-align:top;width:15%;font-size:12px;color:{sal_colour};font-weight:600;">
        {job.salary_raw}
      </td>
      <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;background:{bg};
                 vertical-align:top;width:12%;font-size:11px;color:#555;">
        {location_safe}<br>
        <span style="color:#888;">{job_type_safe}</span>
      </td>
      <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;background:{bg};
                 vertical-align:top;width:34%;font-size:11px;color:#555;line-height:1.5;">
        {desc_safe}
      </td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Azure Jobs Report{label_text}</title>
</head>
<body style="font-family:Arial,Helvetica,sans-serif;background:#f0f2f5;margin:0;padding:20px;">
<div style="max-width:960px;margin:0 auto;">

  <!-- Header -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0078D4;border-radius:8px 8px 0 0;">
    <tr>
      <td style="padding:20px 24px;">
        <div style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">
          Azure Jobs Report{label_text}
        </div>
        <div style="font-size:12px;color:#cce4f7;margin-top:5px;">
          {generated_at} &nbsp;&bull;&nbsp; {len(jobs)} jobs &nbsp;&bull;&nbsp;
          London &amp; South East &nbsp;&bull;&nbsp; £50,000+
        </div>
      </td>
    </tr>
  </table>

  <!-- Jobs table -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#ffffff;border-radius:0 0 8px 8px;
                border:1px solid #e0e0e0;border-top:none;">
    <tr style="background:#f5f5f5;">
      <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:600;
                 color:#555;text-transform:uppercase;letter-spacing:0.5px;
                 border-bottom:2px solid #d0d0d0;">Job Title</th>
      <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:600;
                 color:#555;text-transform:uppercase;letter-spacing:0.5px;
                 border-bottom:2px solid #d0d0d0;">Company</th>
      <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:600;
                 color:#555;text-transform:uppercase;letter-spacing:0.5px;
                 border-bottom:2px solid #d0d0d0;">Salary</th>
      <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:600;
                 color:#555;text-transform:uppercase;letter-spacing:0.5px;
                 border-bottom:2px solid #d0d0d0;">Location</th>
      <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:600;
                 color:#555;text-transform:uppercase;letter-spacing:0.5px;
                 border-bottom:2px solid #d0d0d0;">Description</th>
    </tr>
    {rows_html}
  </table>

  <!-- Footer -->
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
    <tr>
      <td style="text-align:center;font-size:11px;color:#aaa;padding:8px;">
        Sources: Reed &bull; CW Jobs &bull; Totaljobs &bull; Michael Page &bull; JobServe
        &nbsp;|&nbsp; SC Cleared roles excluded &nbsp;|&nbsp; Azure Jobs Scraper
      </td>
    </tr>
  </table>

</div>
</body>
</html>"""


def save_to_html_file(html: str, filepath: str) -> None:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("HTML saved: %s", filepath)

# ── Gmail SMTP Email ──────────────────────────────────────────────────────────


def send_email_report(
    html_body: str,
    subject: str,
    csv_filepath: str,
    gmail_user: str,
    gmail_app_password: str,
    to_email: str,
) -> None:
    """
    Send the HTML report via Gmail SMTP with the CSV as an attachment.
    Requires a Gmail App Password (NOT the Google account password).
    Generate one at: https://myaccount.google.com/apppasswords
    """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email

    # HTML body
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # CSV attachment
    csv_path = Path(csv_filepath)
    if csv_path.exists():
        with open(csv_path, "rb") as f:
            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="{csv_path.name}"',
        )
        msg.attach(attachment)
    else:
        log.warning("CSV file not found for attachment: %s", csv_filepath)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
        log.info("Email sent to %s — subject: %s", to_email, subject)
    except smtplib.SMTPAuthenticationError:
        log.error(
            "Gmail authentication failed. Make sure GMAIL_APP_PASSWORD is a 16-character "
            "App Password, not your Gmail account password. "
            "Generate one at: https://myaccount.google.com/apppasswords"
        )
    except Exception as e:
        log.error("Email send failed: %s", e)

# ── Main Orchestrator ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Azure Jobs Scraper")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and save files but skip sending the email.",
    )
    args = parser.parse_args()

    # Lazy imports after dotenv loaded and Job dataclass defined
    from scrapers.reed import scrape_reed
    from scrapers.cwjobs import scrape_cwjobs
    from scrapers.totaljobs import scrape_totaljobs
    from scrapers.michael_page import scrape_michael_page
    from scrapers.jobserve import scrape_jobserve
    from utils.dedup import deduplicate_jobs

    london_now = datetime.now(LONDON_TZ)
    hour = london_now.hour
    session = "Morning Report" if hour < 12 else "Evening Report"
    date_label = london_now.strftime("%a %d %b %Y")
    subject = f"Azure Jobs {session} \u2014 {date_label}"
    timestamp = london_now.strftime("%Y-%m-%d_%H-%M")

    csv_filepath = OUTPUT_DIR / f"azure_jobs_{timestamp}.csv"
    html_filepath = OUTPUT_DIR / f"azure_jobs_{timestamp}.html"

    log.info("=" * 60)
    log.info("Azure Jobs Scraper — %s %s", session, date_label)
    log.info("=" * 60)

    # ── Run all scrapers ──────────────────────────────────────────────────────
    all_jobs = []
    scrapers = [
        ("Reed",         scrape_reed),
        ("CW Jobs",      scrape_cwjobs),
        ("Totaljobs",    scrape_totaljobs),
        ("Michael Page", scrape_michael_page),
        ("JobServe",     scrape_jobserve),
    ]

    for name, fn in scrapers:
        log.info("── %s ──", name)
        try:
            results = fn()
            log.info("%s: %d jobs collected", name, len(results))
            all_jobs.extend(results)
        except Exception as e:
            log.error("%s scraper error: %s", name, e, exc_info=True)

    log.info("Total before dedup: %d jobs", len(all_jobs))

    if not all_jobs:
        log.warning("No jobs found across all boards. Exiting.")
        sys.exit(0)

    # ── Deduplicate ───────────────────────────────────────────────────────────
    unique_jobs = deduplicate_jobs(all_jobs)
    log.info("Unique jobs after dedup: %d", len(unique_jobs))

    # ── Save outputs ──────────────────────────────────────────────────────────
    save_to_csv(unique_jobs, str(csv_filepath))
    html_body = build_html_report(unique_jobs, session_label=session)
    save_to_html_file(html_body, str(html_filepath))

    log.info("Output files:")
    log.info("  CSV:  %s", csv_filepath)
    log.info("  HTML: %s", html_filepath)

    # ── Send email ────────────────────────────────────────────────────────────
    if args.dry_run:
        log.info("Dry-run mode — email not sent.")
        return

    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    recipient = os.getenv("RECIPIENT_EMAIL", "sufyan@ict-cloud.solutions").strip()

    if not gmail_user or not gmail_pass or gmail_pass.startswith("xxxx"):
        log.error(
            "Gmail credentials not configured. Edit .env and set "
            "GMAIL_USER and GMAIL_APP_PASSWORD, then re-run."
        )
        return

    send_email_report(
        html_body=html_body,
        subject=subject,
        csv_filepath=str(csv_filepath),
        gmail_user=gmail_user,
        gmail_app_password=gmail_pass,
        to_email=recipient,
    )


if __name__ == "__main__":
    main()
