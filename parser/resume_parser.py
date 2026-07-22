import pdfplumber
import docx
import re

from config.defaults import DEFAULT_PROFILE, build_matching_summary, load_applyflow_profile, normalize_profile

KNOWN_SKILLS = [
    "Python",
    "C++",
    "C",
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
    "Machine Learning",
    "Embedded systems",
    "Networking",
    "OSPF",
    "HSRP",
    "SNMP",
]


def extract_text_from_file(filepath: str) -> str:
    if filepath.lower().endswith(".pdf"):
        text = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text)
    elif filepath.lower().endswith(".docx"):
        d = docx.Document(filepath)
        return "\n".join(p.text for p in d.paragraphs)
    else:
        raise ValueError("Unsupported file type. Upload a .pdf or .docx resume.")


def parse_resume_to_profile(resume_text: str) -> dict:
    """
    Deterministic resume parser.

    This intentionally avoids paid LLM APIs. It starts from ApplyFlow's profile.json
    when available, then lightly enriches it from the uploaded resume text.
    """
    base = load_applyflow_profile() or dict(DEFAULT_PROFILE)
    profile = normalize_profile(base)

    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if lines:
        first_line = lines[0]
        if 2 <= len(first_line.split()) <= 5 and "@" not in first_line:
            profile["name"] = first_line

    found_skills = []
    resume_lower = resume_text.lower()
    for skill in KNOWN_SKILLS:
        if skill.lower() in resume_lower and skill not in found_skills:
            found_skills.append(skill)
    profile["skills"] = sorted(set((profile.get("skills") or []) + found_skills))

    education = list(profile.get("education") or [])
    for line in lines:
        lower = line.lower()
        if any(word in lower for word in ("university", "college", "b.sc", "bsc", "b.a", "ba")):
            if not any(line in str(item.values()) for item in education):
                education.append({"degree": "", "field": "", "institution": line, "year": _find_year(line)})
    profile["education"] = education[:8]

    profile["email"] = _find_first(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text)
    profile["phone"] = _find_first(r"(\+?\d[\d\s().-]{7,}\d)", resume_text)
    profile["summary_for_matching"] = build_matching_summary(profile)
    return normalize_profile(profile)


def _find_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(0).strip() if match else ""


def _find_year(text: str) -> str:
    return _find_first(r"(20\d{2}|19\d{2})", text)
