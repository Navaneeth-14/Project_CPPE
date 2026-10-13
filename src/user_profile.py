"""
User profile recommendations.

When a user has selected genre preferences (cold start),
we build a synthetic taste profile from those genres and
run the content model against it. No rating history needed.
"""

from __future__ import annotations
import logging
import pandas as pd

from src.content_model import get_content_scores
from src.config import DEFAULT_TOP_N

logger = logging.getLogger(__name__)

# All genres available for onboarding selection
ALL_GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "IMAX",
    "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
]


def recommend_for_new_user(
    preferred_genres: list[str],
    movies_df: pd.DataFrame,
    genre_matrix: pd.DataFrame,
    top_n: int = DEFAULT_TOP_N,
) -> list[dict]:
    """
    Cold-start recommendations purely from genre preferences.

    Finds seed movies (those whose genres overlap with preferences),
    then scores all candidates by content similarity to those seeds.
    """
    if not preferred_genres:
        return []

    pref_set = set(preferred_genres)

    # Seed pool: movies that match at least one preferred genre
    def overlap(genre_list):
        if not isinstance(genre_list, (list, __import__('numpy').ndarray)):
            return 0
        return len(set(list(genre_list)) & pref_set)

    overlap_scores = movies_df["genres"].apply(overlap)
    seed_ids = overlap_scores[overlap_scores > 0].nlargest(50).index.tolist()

    if not seed_ids:
        logger.warning("No seed movies found for genres: %s", preferred_genres)
        return []

    candidate_ids = movies_df.index.tolist()
    content_scores = get_content_scores(candidate_ids, seed_ids, genre_matrix)

    top = content_scores.sort_values(ascending=False).head(top_n)

    results = []
    for movie_id, score in top.items():
        if movie_id not in movies_df.index:
            continue
        row = movies_df.loc[movie_id]
        results.append({
            "movieId": int(movie_id),
            "title": row["title"],
            "genres": list(row["genres"]) if hasattr(row["genres"], '__iter__') else [],
            "content_score": round(float(score), 4),
            "collab_score": 0.0,
            "hybrid_score": round(float(score), 4),
        })

    return results
