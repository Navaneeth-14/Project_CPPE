"""
Hybrid recommender: combines content-based and collaborative signals into
a single ranked list of recommendations for a given user.
"""

import logging
import pandas as pd

from src.config import DEFAULT_TOP_N, CONTENT_WEIGHT, COLLAB_WEIGHT
from src.content_model import get_content_scores
from src.collaborative_model import get_collaborative_scores

logger = logging.getLogger(__name__)


def recommend(
    user_id: int,
    movies_df: pd.DataFrame,
    ratings_df: pd.DataFrame,
    genre_matrix: pd.DataFrame,
    user_movie_matrix: pd.DataFrame,
    top_n: int = DEFAULT_TOP_N,
) -> list[dict]:
    """
    Return top_n movie recommendations for user_id.

    Each result dict contains:
      - movieId, title, genres
      - content_score (genre similarity to user's rated movies)
      - collab_score  (weighted prediction from similar users)
      - hybrid_score  (weighted blend of the two)

    Strategy:
      1. Exclude movies the user has already rated.
      2. Score candidates via content-based and collaborative models.
      3. Blend scores with configured weights.
      4. Return top_n by hybrid score.
    """
    # Movies this user has already rated
    user_ratings = ratings_df[ratings_df["userId"] == user_id]
    if user_ratings.empty:
        logger.warning(f"No ratings found for user {user_id}")
        return []

    rated_ids = set(user_ratings["movieId"].tolist())

    # Candidate pool: all movies not yet rated by this user
    all_movie_ids = movies_df.index.tolist()
    candidates = [m for m in all_movie_ids if m not in rated_ids]

    if not candidates:
        logger.warning(f"User {user_id} has rated every movie")
        return []

    logger.debug(f"User {user_id}: {len(rated_ids)} rated, {len(candidates):,} candidates")

    # ── Content scores ────────────────────────────────────────────────────────
    content_scores = get_content_scores(
        candidate_movie_ids=candidates,
        rated_movie_ids=list(rated_ids),
        genre_matrix=genre_matrix,
    )

    # ── Collaborative scores ──────────────────────────────────────────────────
    collab_scores = get_collaborative_scores(
        user_id=user_id,
        candidate_movie_ids=candidates,
        matrix=user_movie_matrix,
    )

    # ── Hybrid blend ──────────────────────────────────────────────────────────
    hybrid = (
        CONTENT_WEIGHT * content_scores
        + COLLAB_WEIGHT * collab_scores
    )
    hybrid = hybrid.sort_values(ascending=False).head(top_n)

    # ── Build result list ─────────────────────────────────────────────────────
    results = []
    for movie_id, h_score in hybrid.items():
        if movie_id not in movies_df.index:
            continue
        row = movies_df.loc[movie_id]
        results.append({
            "movieId": int(movie_id),
            "title": row["title"],
            "genres": row["genres"] if isinstance(row["genres"], list) else row["genres"].tolist(),
            "content_score": round(float(content_scores.get(movie_id, 0.0)), 4),
            "collab_score": round(float(collab_scores.get(movie_id, 0.0)), 4),
            "hybrid_score": round(float(h_score), 4),
        })

    return results
