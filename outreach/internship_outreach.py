import argparse
import csv
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config.defaults import load_applyflow_profile
from outreach.company_contacts import best_email_for_company, load_contacts


DEFAULT_COMPANIES_PATH = Path(__file__).resolve().parents[2] / "ApplyFlow" / "remote_companies.json"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "internship_outreach_drafts.csv"

SUBJECT = "Internship inquiry - Computer Engineering graduate"
JOB_SUBJECT = "Application inquiry - internship/junior software role"


def build_email(company: str, profile: dict) -> str:
    name = profile.get("name", "Eyobel Zeleke Berie")
    skills_raw = (profile.get("skills") or [])[:8]
    skill_levels = profile.get("skill_levels") or {}
    _level_labels = {1: "familiar with", 2: "proficient in", 3: "expert in"}
    if skill_levels:
        skill_parts = []
        for s in skills_raw:
            lbl = _level_labels.get(skill_levels.get(s, 0), "")
            skill_parts.append(f"{s} ({lbl})" if lbl else s)
        skills = ", ".join(skill_parts)
    else:
        skills = ", ".join(skills_raw)
    website = profile.get("website", "")
    portfolio_line = f"\nPortfolio: {website}" if website else ""
    return (
        f"Hello {company} team,\n\n"
        f"My name is {name}. I am a Computer Engineering graduate based in Ethiopia, and I am looking for an internship or junior opportunity where I can contribute, learn quickly, and grow with a strong engineering team.\n\n"
        f"My background includes {skills}, with hands-on project experience in embedded AI (TinyML on Arduino), FastAPI backends, React dashboards, PostgreSQL, Spring Boot, and network engineering. I am especially interested in backend, full-stack, embedded AI, Python, or junior software engineering work.\n\n"
        "I wanted to ask politely if your team has any internship openings, trainee roles, apprenticeship-style opportunities, or even an unpaid internship where I could prove myself through useful work. I would be grateful for the chance to contribute to a real project and learn from your engineers.\n\n"
        f"I can share my resume, GitHub, or complete a small trial task if that helps.{portfolio_line}\n\n"
        "Thank you for your time and consideration.\n\n"
        f"Best regards,\n{name}"
    )


def build_job_email(company_or_role: str, job_text: str, profile: dict) -> tuple[str, str]:
    name = profile.get("name", "Eyobel Zeleke Berie")
    skills = ", ".join((profile.get("skills") or [])[:8])
    focus = _infer_focus(job_text)
    target = company_or_role.strip() or "your team"
    subject = f"{JOB_SUBJECT} at {target}" if target != "your team" else JOB_SUBJECT
    body = (
        f"Hello {target} team,\n\n"
        f"My name is {name}. I am writing to ask about the internship or junior opportunity you shared. "
        f"My background is in Computer Engineering, and I am especially interested in contributing to {focus} work while learning from a strong engineering team.\n\n"
        f"I have hands-on experience with {skills}. My recent work includes embedded AI with TinyML, FastAPI backends, React dashboards, PostgreSQL, Spring Boot services, and network engineering. "
        "I am comfortable learning quickly, taking ownership of small features, and doing careful implementation work.\n\n"
        "If this role is still open, I would be grateful for the chance to apply. I am also open to internship, trainee, apprenticeship, junior, or unpaid internship arrangements if there is meaningful project work and mentorship.\n\n"
        "I can share my resume, portfolio, GitHub, or complete a small trial task if useful.\n\n"
        "Thank you for your time and consideration.\n\n"
        f"Best regards,\n{name}"
    )
    return subject, body


def load_companies(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [str(item).strip() for item in data if str(item).strip()]


def build_company_rows(companies: list[str], profile: dict) -> list[dict]:
    contacts = load_contacts()
    return [
        {
            "company": company,
            "email": best_email_for_company(company, contacts),
            "subject": SUBJECT,
            "body": build_email(company, profile),
        }
        for company in companies
    ]


def write_rows(rows: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "email", "subject", "body"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def generate_company_drafts(limit: int = 50, companies_path: Path = DEFAULT_COMPANIES_PATH, output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    profile = load_applyflow_profile() or {}
    companies = load_companies(companies_path)[:limit]
    return write_rows(build_company_rows(companies, profile), output_path)


# --------------------------------------------------------------------------- #
# SMTP email sending
# --------------------------------------------------------------------------- #

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")


def smtp_configured() -> bool:
    return bool(EMAIL_FROM and EMAIL_PASSWORD)


def send_email(to_email: str, subject: str, body: str, from_email: str = "", password: str = "") -> None:
    """
    Send a plain-text email via SMTP (Gmail by default).
    Raises on failure so the caller can decide how to handle it.
    """
    sender = from_email or EMAIL_FROM
    pwd = password or EMAIL_PASSWORD
    if not sender or not pwd:
        raise RuntimeError(
            "EMAIL_FROM and EMAIL_PASSWORD environment variables are not set. "
            "Add them to your .env / Render env vars to enable email sending."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, [to_email], msg.as_string())


def send_company_outreach(company: str, profile: dict | None = None) -> tuple[bool, str, str]:
    """
    Build and send the internship inquiry email for one company.
    Returns (success: bool, email_used: str, error_message: str).
    """
    if profile is None:
        profile = load_applyflow_profile() or {}
    best_email = best_email_for_company(company)
    if not best_email:
        return False, "", f"No email found for {company}. Run /findemail {company} first."
    subject = SUBJECT
    body = build_email(company, profile)
    try:
        send_email(best_email, subject, body)
        return True, best_email, ""
    except Exception as exc:
        return False, best_email, str(exc)


def bulk_send_outreach(
    limit: int = 50,
    companies_path: Path = DEFAULT_COMPANIES_PATH,
    progress_callback=None,
) -> list[dict]:
    """
    Send internship outreach emails to the first `limit` companies that have a
    known email in company_contacts.json.
    progress_callback(i, total, company, success, email, error) is called for each.
    Returns a list of result dicts.
    """
    profile = load_applyflow_profile() or {}
    companies = load_companies(companies_path)[:limit]
    contacts = load_contacts()
    results = []
    sendable = [
        c for c in companies if best_email_for_company(c, contacts)
    ]
    total = len(sendable)
    for i, company in enumerate(sendable, 1):
        ok, email_used, err = send_company_outreach(company, profile)
        results.append({"company": company, "email": email_used, "success": ok, "error": err})
        if progress_callback:
            progress_callback(i, total, company, ok, email_used, err)
    return results


def _infer_focus(job_text: str) -> str:
    text = job_text.lower()
    if any(term in text for term in ("embedded", "iot", "arduino", "firmware", "tinyml", "edge ai")):
        return "embedded AI and hardware-connected software"
    if any(term in text for term in ("backend", "api", "fastapi", "django", "postgres", "database")):
        return "backend engineering and API development"
    if any(term in text for term in ("react", "frontend", "front-end", "javascript", "typescript")):
        return "full-stack and frontend development"
    if any(term in text for term in ("network", "linux", "devops", "infrastructure")):
        return "networking, Linux, and infrastructure work"
    if any(term in text for term in ("machine learning", "ml", "ai", "data")):
        return "AI and applied machine learning"
    return "software engineering"


def main():
    parser = argparse.ArgumentParser(description="Generate internship outreach email drafts.")
    parser.add_argument("--companies", type=Path, default=DEFAULT_COMPANIES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    output = generate_company_drafts(args.limit, args.companies, args.output)
    print(f"Wrote outreach drafts to {output}")


if __name__ == "__main__":
    main()
