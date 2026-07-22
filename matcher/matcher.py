import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer

MATCH_THRESHOLD = float(os.environ.get("MATCH_THRESHOLD", 0.55))
KEYWORD_MATCH_THRESHOLD = int(os.environ.get("KEYWORD_MATCH_THRESHOLD", 50))

POSITIVE_TERMS = {
    "internship": 14,
    "intern": 14,
    "junior": 12,
    "entry level": 10,
    "graduate": 8,
    "trainee": 8,
    "remote": 10,
    "ethiopia": 10,
    "east africa": 8,
    "africa": 6,
    "python": 7,
    "fastapi": 7,
    "react": 7,
    "javascript": 5,
    "java": 5,
    "spring boot": 6,
    "postgresql": 5,
    "c++": 5,
    "arduino": 6,
    "embedded": 8,
    "machine learning": 7,
    "ai": 5,
    "backend": 7,
    "full-stack": 7,
    "software engineer": 7,
    "network": 5,
    "scholarship": 8,
    "fellowship": 8,
}

NEGATIVE_TERMS = {
    "senior": 16,
    "lead engineer": 12,
    "5+ years": 18,
    "five years": 18,
    "7+ years": 20,
    "10+ years": 25,
    "onsite only": 10,
    "us citizens only": 18,
    "security clearance": 20,
}

# all-MiniLM-L6-v2: small, fast, free, runs fine on CPU. Downloads once (~90MB) on first run.
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> list:
    model = get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def cosine_sim(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b))  # already normalized, so dot product = cosine similarity


def is_match(post_embedding: list, profile_embedding: list) -> tuple[bool, float]:
    score = cosine_sim(post_embedding, profile_embedding)
    return score >= MATCH_THRESHOLD, score


def keyword_score(post_text: str, profile_json: dict | None = None) -> int:
    text = post_text.lower()
    score = 0
    for term, points in POSITIVE_TERMS.items():
        if term in text:
            score += points

    if profile_json:
        for skill in profile_json.get("skills") or []:
            if str(skill).lower() in text:
                score += 3
        for role in profile_json.get("target_roles") or []:
            for token in _important_tokens(str(role)):
                if token in text:
                    score += 2

    for term, points in NEGATIVE_TERMS.items():
        if term in text:
            score -= points

    year_requirement = re.search(r"(\d+)\+?\s*(?:years|yrs)", text)
    if year_requirement and int(year_requirement.group(1)) >= 4:
        score -= 18

    return max(0, min(100, score))


def is_hardcoded_match(post_text: str, profile_json: dict | None = None) -> tuple[bool, int]:
    score = keyword_score(post_text, profile_json)
    return score >= KEYWORD_MATCH_THRESHOLD, score


def combined_match(post_text: str, post_embedding: list, profile_embedding: list, profile_json: dict | None = None) -> tuple[bool, float, int]:
    semantic_match, semantic_score = is_match(post_embedding, profile_embedding)
    rules_match, rules_score = is_hardcoded_match(post_text, profile_json)
    combined_score = (semantic_score * 100 * 0.55) + (rules_score * 0.45)
    return semantic_match or rules_match or combined_score >= 55, combined_score / 100, rules_score


def _important_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9+#.-]+", value.lower())
        if len(token) >= 4 and token not in {"intern", "junior", "developer", "engineer"}
    ]
