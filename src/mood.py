"""
Mood-based filtering layer.

Maps human moods to genre clusters, then re-weights candidate scores
so movies matching the mood float to the top.
"""

from __future__ import annotations
import pandas as pd

# ── Mood → genre cluster map ──────────────────────────────────────────────────
# Each mood boosts movies that contain ANY of the listed genres.
MOOD_GENRES: dict[str, list[str]] = {
    "something_light":   ["Comedy", "Animation", "Family", "Musical"],
    "intense":           ["Thriller", "Crime", "Mystery", "Action"],
    "mind_bending":      ["Sci-Fi", "Mystery", "Fantasy", "Thriller"],
    "feel_good":         ["Comedy", "Romance", "Adventure", "Family"],
    "emotional":         ["Drama", "Romance"],
    "action_packed":     ["Action", "Adventure", "War"],
    "dark_and_gritty":   ["Crime", "Drama", "Thriller", "War", "Horror"],
    "something_classic": ["Drama", "Romance", "Mystery"],
}

# Human-readable labels for the UI
MOOD_LABELS: dict[str, str] = {
    "something_light":   "😄 Something Light",
    "intense":           "😤 Intense",
    "mind_bending":      "🤯 Mind-Bending",
    "feel_good":         "🥰 Feel-Good",
    "emotional":         "😢 Emotional",
    "action_packed":     "💥 Action-Packed",
    "dark_and_gritty":   "🌑 Dark & Gritty",
    "something_classic": "🎩 Something Classic",
}

BOOST_FACTOR = 0.25  # added to hybrid_score when movie matches mood


def list_moods() -> list[dict]:
    """Return all moods with their keys and labels — used by the /moods endpoint."""
    return [{"key": k, "label": v} for k, v in MOOD_LABELS.items()]


def apply_mood_boost(
    recommendations: list[dict],
    mood: str,
) -> list[dict]:
    """
    Re-rank recommendations by applying a score boost to movies whose
    genres overlap with the selected mood cluster.

    Returns a new sorted list — original dicts are not mutated.
    """
    if mood not in MOOD_GENRES:
        return recommendations

    target_genres = set(MOOD_GENRES[mood])

    boosted = []
    for rec in recommendations:
        rec_genres = set(rec.get("genres", []) if isinstance(rec.get("genres"), list) else list(rec.get("genres", [])))
        match = bool(rec_genres & target_genres)
        boosted_score = round(rec["hybrid_score"] + (BOOST_FACTOR if match else 0.0), 4)
        boosted.append({**rec, "hybrid_score": boosted_score, "mood_match": match})

    return sorted(boosted, key=lambda r: r["hybrid_score"], reverse=True)
