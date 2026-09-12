"""
CV match scoring: rank scraped jobs by keyword overlap with Sufyan's CV.

Simple, deterministic keyword scoring (no external API calls) so it stays
fast and free to run on every scrape:
  - CORE_SKILLS  — Sufyan's strongest, most senior areas (heavier weight,
    plus a bonus if the keyword appears in the job title, not just the body).
  - SECONDARY_SKILLS — supporting skills (lighter weight).
  - MISMATCH_KEYWORDS — signals the role is a different discipline or
    seniority (service desk, junior/graduate, or application development),
    penalised so they sort to the bottom even with a good day rate.
"""

CORE_SKILLS = [
    "azure landing zone", "landing zone", "terraform", "bicep", "arm template",
    "azure policy", "gitops", "devsecops", "iac", "infrastructure as code",
    "entra id", "conditional access", "privileged identity management", "pim",
    "rbac", "managed identit", "key vault", "zero trust", "identity and access",
    "iam", "microsoft sentinel", "sentinel", "defender for cloud",
    "azure monitor", "application insights", "log analytics", "observability",
    "aiops", "microsoft purview", "data governance", "dlp",
    "solutions architect", "cloud architect", "infrastructure architect",
    "security architect", "cybersecurity architect", "aks", "kubernetes",
    "cost optimisation", "cost optimization", "azure governance",
]

SECONDARY_SKILLS = [
    "powershell", "bash", "azure devops", "github actions", "ci/cd",
    "windows server", "active directory", "vmware", "hyper-v", "veeam",
    "azure site recovery", "azure backup", "hub-and-spoke", "expressroute",
    "azure firewall", "nsg", "vpn", "rhel", "ubuntu", "linux", "sql server",
    "aws", "ec2", "vpc", "itil", "iso27001", "nist", "cis controls",
    "copilot", "retrieval-augmented generation", "rag", "ai agent",
    "microsoft foundry", "docker", "azure functions",
]

MISMATCH_KEYWORDS = [
    "service desk", "help desk", "helpdesk", "1st line", "2nd line",
    "3rd line", "first line", "second line", "third line",
    "junior", "graduate", "trainee", "intern",
    "software developer", "software engineer", "front-end", "frontend",
    "front end", "back-end developer", "full stack", "web developer",
    "react developer", ".net developer", "java developer", "qa engineer",
    "test engineer", "data scientist", "data analyst",
]

CORE_WEIGHT = 3
TITLE_BONUS = 2
SECONDARY_WEIGHT = 1
MISMATCH_PENALTY = 4


def score_job(job) -> int:
    """Score a Job by keyword overlap with the CV. Higher is a better fit."""
    title = (job.title or "").lower()
    text = f"{title} {(job.description or '').lower()}"

    core_hits = 0
    score = 0
    for kw in CORE_SKILLS:
        if kw in text:
            score += CORE_WEIGHT
            core_hits += 1
            if kw in title:
                score += TITLE_BONUS
    for kw in SECONDARY_SKILLS:
        if kw in text:
            score += SECONDARY_WEIGHT
    for kw in MISMATCH_KEYWORDS:
        if kw in text:
            score -= MISMATCH_PENALTY

    if core_hits == 0:
        # No genuine Azure/architecture-specific signal at all — cap so
        # generic secondary-keyword overlap alone can never read as a
        # real match (this is what let non-Azure roles through before).
        score = min(score, 0)

    return score


def match_label(score: int) -> str:
    """Bucket a score into a display label."""
    if score >= 12:
        return "Strong"
    if score >= 5:
        return "Good"
    if score >= 1:
        return "Fair"
    return "Low"
