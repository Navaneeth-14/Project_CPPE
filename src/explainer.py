"""
GenAI explainer: generates a short natural-language explanation for each recommendation.

Supports Groq, OpenAI, and Anthropic. Provider is selected via GENAI_PROVIDER in config.
Groq and OpenAI share the same client (Groq's API is OpenAI-compatible).
Each explanation is requested as structured JSON so the frontend can render it cleanly.
"""

import json
import logging

from src.config import (
    GENAI_PROVIDER,
    GENAI_MODEL,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
)

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(user_id: int, recommendations: list[dict]) -> str:
    rec_lines = "\n".join(
        f"  - movieId {r['movieId']}: \"{r['title']}\" "
        f"(genres: {', '.join(r['genres'])}, "
        f"content_score: {r['content_score']}, collab_score: {r['collab_score']})"
        for r in recommendations
    )

    return f"""You are a movie recommendation assistant. A user (ID {user_id}) has received these recommendations from a hybrid recommender system that combines genre similarity (content_score) and collaborative filtering from similar users (collab_score):

{rec_lines}

For each movie, write a 1–2 sentence explanation of why it was recommended, referencing:
1. The genre fit (content_score reflects how well the genres match the user's taste)
2. The community signal (collab_score reflects how strongly similar users liked it)

Respond ONLY with a valid JSON array. No extra text, no markdown code fences. Format:
[
  {{
    "movieId": <int>,
    "explanation": "<1-2 sentences>"
  }},
  ...
]"""


# ── Provider calls ────────────────────────────────────────────────────────────

def _call_groq(prompt: str) -> str:
    """Groq uses the OpenAI SDK with a custom base_url — no extra package needed."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    response = client.chat.completions.create(
        model=GENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
    )
    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=GENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
    )
    return response.choices[0].message.content.strip()


def _call_anthropic(prompt: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=GENAI_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ── Public interface ──────────────────────────────────────────────────────────

def explain_recommendations(
    user_id: int,
    recommendations: list[dict],
) -> list[dict]:
    """
    Call the configured GenAI provider and attach an 'explanation' field
    to each recommendation dict. Returns the enriched list.

    On any error (missing API key, network failure, bad JSON), falls back
    gracefully: each recommendation gets a placeholder explanation.
    """
    if not recommendations:
        return recommendations

    prompt = _build_prompt(user_id, recommendations)

    try:
        if GENAI_PROVIDER == "groq":
            raw = _call_groq(prompt)
        elif GENAI_PROVIDER == "anthropic":
            raw = _call_anthropic(prompt)
        else:
            raw = _call_openai(prompt)

        explanations: list[dict] = json.loads(raw)
        exp_by_id: dict[int, str] = {
            e["movieId"]: e["explanation"] for e in explanations
        }
    except Exception as exc:
        logger.error(f"GenAI explanation failed: {exc}")
        exp_by_id = {}

    enriched = []
    for rec in recommendations:
        rec_copy = dict(rec)
        rec_copy["explanation"] = exp_by_id.get(
            rec["movieId"],
            (
                f"Recommended based on genre similarity "
                f"(content score: {rec['content_score']}) and "
                f"ratings from users with similar taste "
                f"(collab score: {rec['collab_score']})."
            ),
        )
        enriched.append(rec_copy)

    return enriched
