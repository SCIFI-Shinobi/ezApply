import json
import os
from pathlib import Path

# Skill level labels used when building the matching summary
_LEVEL_LABELS = {1: "familiar with", 2: "proficient in", 3: "expert in"}


DEFAULT_CHANNELS = [
    {"username": "OHUB4AllET", "kind": "scholarship"},
    {"username": "Tegegnpathway", "kind": "scholarship"},
    {"username": "ethio_job_vacancy1", "kind": "job"},
    {"username": "harmeejobs", "kind": "job"},
    {"username": "jobs_in_ethio", "kind": "job"},
]

DEFAULT_TARGET_ROLES = [
    "Software Engineering Intern",
    "Backend Developer Intern",
    "Full-Stack Developer Intern",
    "Embedded AI Engineer Intern",
    "Junior Python Developer",
    "Junior FastAPI Developer",
    "Junior React Developer",
    "Junior Java Developer",
    "Network Engineering Intern",
]

DEFAULT_LOCATION_PREFERENCES = [
    "Remote",
    "Ethiopia",
    "East Africa",
    "Africa",
    "Relocation supported",
]

DEFAULT_PROFILE = {
    "name": "Eyobel Zeleke Berie",
    "target_roles": DEFAULT_TARGET_ROLES,
    "skills": [
        "Python",
        "C/C++",
        "Arduino",
        "React",
        "FastAPI",
        "PostgreSQL",
        "Spring Boot",
        "RESTful APIs",
        "Git",
        "Linux",
        "Docker",
        "Java",
        "JavaScript",
        "TinyML",
        "Embedded systems",
        "Networking",
    ],
    "education": [
        {
            "degree": "B.Sc.",
            "field": "Computer Engineering",
            "institution": "Bahir Dar University",
            "year": "2026",
        },
        {
            "degree": "B.A.",
            "field": "Accounting and Finance",
            "institution": "Blue Mark College",
            "year": "2026",
        },
    ],
    "experience": [
        {
            "title": "Lead Developer",
            "org": "Mango Guard",
            "summary": "Built a TinyML plant health monitoring system with Arduino Nano 33 BLE Sense, Raspberry Pi gateway, FastAPI backend, React dashboard, and disease forecasting.",
            "duration": "2025-08 to 2026-05",
        },
        {
            "title": "Network Engineering Intern",
            "org": "Injibara University ICT Executive",
            "summary": "Designed OSPF and HSRP network architecture, deployed SNMP monitoring, and handled structured cabling and access point provisioning.",
            "duration": "2025-04 to 2025-06",
        },
    ],
    "projects": [
        {
            "name": "Mango Guard",
            "summary": "Edge AI agriculture system connecting embedded inference, backend APIs, forecasting, and a web dashboard.",
        },
        {
            "name": "Hotel Management System",
            "summary": "Spring Boot and PostgreSQL backend with JWT authentication and booking workflows.",
        },
        {
            "name": "Wubet Digital Platform",
            "summary": "React marketplace MVP for Ethiopian fashion designers.",
        },
    ],
    "location_preference": DEFAULT_LOCATION_PREFERENCES,
    "summary_for_matching": (
        "Computer Engineering graduate targeting remote, Ethiopia-based, and East Africa-friendly internships or junior roles in software engineering, "
        "backend development, full-stack development, embedded AI, and network engineering. Skilled in Python, FastAPI, React, JavaScript, Java, "
        "Spring Boot, PostgreSQL, C/C++, Arduino, TinyML, Linux, Docker, REST APIs, Git, and networking. Built production-grade projects spanning "
        "embedded AI plant health monitoring, RESTful backends, React dashboards, marketplace systems, and resilient campus network design. "
        "Especially interested in internships, junior roles, mentorship-heavy opportunities, and unpaid internships when they provide meaningful learning."
    ),
}


def parse_channel_username(value: str) -> str:
    cleaned = value.strip()
    cleaned = cleaned.replace("https://t.me/", "").replace("http://t.me/", "")
    cleaned = cleaned.replace("https://telegram.me/", "").replace("http://telegram.me/", "")
    cleaned = cleaned.replace("t.me/", "")
    cleaned = cleaned.lstrip("@").strip("/")
    return cleaned.split("/")[0]


def normalize_profile(profile: dict) -> dict:
    merged = dict(DEFAULT_PROFILE)
    merged.update({k: v for k, v in profile.items() if v not in (None, "", [], {})})
    merged.setdefault("target_roles", DEFAULT_TARGET_ROLES)
    merged.setdefault("location_preference", DEFAULT_LOCATION_PREFERENCES)
    merged["summary_for_matching"] = merged.get("summary_for_matching") or build_matching_summary(merged)
    return merged


def build_matching_summary(profile: dict) -> str:
    # Use skill_levels dict if available for richer context
    skill_levels = profile.get("skill_levels") or {}
    raw_skills = profile.get("skills") or []
    if skill_levels:
        skill_parts = []
        for s in raw_skills:
            label = _LEVEL_LABELS.get(skill_levels.get(s, 0), "")
            skill_parts.append(f"{s} ({label})" if label else s)
        skills_str = ", ".join(skill_parts)
    else:
        skills_str = ", ".join(raw_skills)
    roles = ", ".join(profile.get("target_roles") or [])
    locations = ", ".join(profile.get("location_preference") or [])
    experience_bits = []
    for item in profile.get("experience") or []:
        title = item.get("title", "")
        org = item.get("org", "")
        summary = item.get("summary", "")
        experience_bits.append(f"{title} at {org}: {summary}".strip())
    projects = []
    for item in profile.get("projects") or []:
        projects.append(f"{item.get('name', '')}: {item.get('summary', '')}".strip())
    return (
        f"{profile.get('name', 'Candidate')} is targeting {roles}. "
        f"Core skills: {skills_str}. Location preferences: {locations}. "
        f"Experience: {' '.join(experience_bits)} Projects: {' '.join(projects)}"
    ).strip()


def applyflow_profile_path() -> Path:
    override = os.environ.get("APPLYFLOW_PROFILE_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "ApplyFlow" / "profile.json"


def load_applyflow_profile() -> dict | None:
    path = applyflow_profile_path()
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        source = json.load(f)

    personal = source.get("personal", {})
    raw_skills = source.get("skills", [])
    skill_names = [s.get("name") for s in raw_skills if s.get("name")]
    # Preserve skill levels (1=familiar, 2=proficient, 3=expert) from profile.json
    skill_levels = {s["name"]: s["level"] for s in raw_skills if s.get("name") and s.get("level")}

    return normalize_profile(
        {
            "name": personal.get("fullName"),
            "email": personal.get("email", ""),
            "phone": personal.get("phone", ""),
            "website": personal.get("website", ""),
            "location": personal.get("location", ""),
            "target_roles": DEFAULT_TARGET_ROLES,
            "skills": skill_names,
            "skill_levels": skill_levels,  # {skill_name: level_int}
            "education": [
                {
                    "degree": ed.get("degree", ""),
                    "field": ed.get("field", ""),
                    "institution": ed.get("school", ""),
                    "year": ed.get("graduationYear", ""),
                }
                for ed in source.get("education", [])
            ],
            "experience": [
                {
                    "title": exp.get("title", ""),
                    "org": exp.get("company", ""),
                    "summary": exp.get("description", ""),
                    "duration": f"{exp.get('startDate', '')} to {exp.get('endDate', '')}".strip(),
                }
                for exp in source.get("experience", [])
            ],
            "projects": DEFAULT_PROFILE["projects"],
            "location_preference": DEFAULT_LOCATION_PREFERENCES,
            "summary_for_matching": source.get("summary"),
        }
    )


def applyflow_channels_path() -> Path:
    """Optional channels.json next to profile.json in the ApplyFlow folder."""
    override = os.environ.get("APPLYFLOW_PROFILE_PATH")
    if override:
        base = Path(override).parent
    else:
        base = Path(__file__).resolve().parents[2] / "ApplyFlow"
    return base / "channels.json"


def load_applyflow_channels() -> list[dict]:
    """
    Load extra channels from ApplyFlow/channels.json if it exists.
    Expected format: [{"username": "channelname", "kind": "job"}]
    or a plain list of t.me URLs / @usernames (kind defaults to 'job').
    """
    path = applyflow_channels_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        result = []
        for item in data:
            if isinstance(item, dict):
                username = parse_channel_username(item.get("username", ""))
                kind = item.get("kind", "job")
            else:
                username = parse_channel_username(str(item))
                kind = "job"
            if username:
                result.append({"username": username, "kind": kind})
        return result
    except Exception:
        return []
