"""
Generate a tailored CV-tweak summary and cover letter draft for a single
job, via the Claude API. Called only for "Strong" CV-match jobs (see
utils/match.py) to keep API spend low on a script that runs twice daily.
"""
import logging

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 2048

SYSTEM_PROMPT = (
    "You are a career coach helping a senior Azure infrastructure engineer "
    "tailor his CV and write a cover letter for one specific job listing. "
    "Be concise and concrete, and never invent experience, employers, or "
    "achievements that are not in the CV provided. "
    "Output exactly two Markdown sections, in this order:\n"
    "## CV Tweaks\n"
    "A short bulleted list of specific rewordings, reorderings, or "
    "emphasis changes to foreground the CV experience most relevant to "
    "this job — not a rewritten CV, just the adjustments.\n"
    "## Cover Letter\n"
    "A complete, ready-to-send cover letter (3-4 paragraphs, no "
    "placeholder brackets like [Company Name])."
)


def generate_application_kit(client, cv_text: str, job) -> str:
    """
    Call the Claude API for one job. Returns the Markdown response text.
    Raises on API error — callers should catch per-job so one failure
    doesn't stop the run.
    """
    user_message = (
        f"CV:\n{cv_text}\n\n"
        "---\n\n"
        f"Job title: {job.title}\n"
        f"Company: {job.company or 'Not specified'}\n"
        f"Location: {job.location}\n"
        f"Salary: {job.salary_raw}\n"
        f"Description:\n{job.description or '(no description provided)'}\n"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return "".join(block.text for block in response.content if block.type == "text")
