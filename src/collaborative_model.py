"""
Collaborative filtering model: user–user similarity based on rating patterns.

Uses a sparse user-movie rating matrix and cosine similarity between user vectors.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from src import storage
from src.config import USER_MOVIE_MATRIX_FILE

logger = logging.getLogger(__name__)


# ── Build ─────────────────────────────────────────────────────────────────────

def build_user_movie_matrix(ratings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot ratings into a user × movie matrix (mean-centered per user).
    NaN = movie not rated by that user.
    Saved to disk via storage layer.
    """
    logger.info("Building user–movie matrix...")

    matrix = ratings_df.pivot_table(
        index="userId", columns="movieId", values="rating"
    )

    # Mean-center each user's ratings (removes user-level bias)
    user_means = matrix.mean(axis=1)
    matrix_centered = matrix.sub(user_means, axis=0)

    storage.save_dataframe(matrix_centered, USER_MOVIE_MATRIX_FILE)
    logger.info(f"  User–movie matrix: {matrix_centered.shape[0]:,} users × {matrix_centered.shape[1]:,} movies")
    return matrix_centered


def load_user_movie_matrix() -> pd.DataFrame:
    return storage.load_dataframe(USER_MOVIE_MATRIX_FILE)


# ── Query ─────────────────────────────────────────────────────────────────────

def get_similar_users(
    user_id: int,
    matrix: pd.DataFrame,
    top_k: int = 30,
) -> pd.Series:
    """
    Return the top-k most similar users to user_id by cosine similarity
    on their mean-centered rating vectors.
    """
    if user_id not in matrix.index:
        return pd.Series(dtype=float)

    # Fill NaN with 0 for similarity computation (unrated = neutral)
    filled = matrix.fillna(0)
    target = filled.loc[[user_id]].values          # (1, M)
    all_users = filled.values                       # (U, M)

    sims = cosine_similarity(target, all_users).flatten()
    sim_series = pd.Series(sims, index=matrix.index)

    # Exclude the target user itself
    sim_series = sim_series.drop(user_id, errors="ignore")
    return sim_series.nlargest(top_k)


def get_collaborative_scores(
    user_id: int,
    candidate_movie_ids: list[int],
    matrix: pd.DataFrame,
    top_k: int = 30,
) -> pd.Series:
    """
    Predict scores for candidate movies using weighted average of similar users' ratings.

    For each candidate movie, the predicted rating is:
        Σ (sim(u, v) * rating(v, movie)) / Σ |sim(u, v)|
    over similar users who have rated that movie.

    Returns a Series indexed by movieId, values roughly in [0.5, 5.0].
    """
    similar_users = get_similar_users(user_id, matrix, top_k=top_k)
    if similar_users.empty:
        return pd.Series(0.0, index=candidate_movie_ids)

    neighbor_ids = similar_users.index.tolist()
    neighbor_sims = similar_users.values  # shape (K,)

    # Raw (non-centered) ratings of neighbors for candidate movies
    # We work on the centered matrix here; actual score = mean + prediction
    neighbor_matrix = matrix.loc[neighbor_ids, :]   # (K, M)
    candidates_in_matrix = [m for m in candidate_movie_ids if m in matrix.columns]

    if not candidates_in_matrix:
        return pd.Series(0.0, index=candidate_movie_ids)

    sub = neighbor_matrix[candidates_in_matrix]     # (K, C)

    # Weighted sum: ignore NaN by masking
    mask = sub.notna().values.astype(float)         # (K, C)  1 if rated else 0
    values = sub.fillna(0).values                   # (K, C)

    weights = neighbor_sims[:, np.newaxis]          # (K, 1)
    weighted_sum = (weights * values * mask).sum(axis=0)
    weight_total = (np.abs(weights) * mask).sum(axis=0)

    with np.errstate(invalid="ignore", divide="ignore"):
        predicted = np.where(weight_total > 0, weighted_sum / weight_total, np.nan)

    scores = pd.Series(predicted, index=candidates_in_matrix)

    # Normalize to [0, 1] for hybrid blending
    valid = scores.dropna()
    if valid.empty:
        return pd.Series(0.0, index=candidate_movie_ids)

    min_s, max_s = valid.min(), valid.max()
    if max_s > min_s:
        scores = (scores - min_s) / (max_s - min_s)
    else:
        scores = scores.fillna(0).clip(0, 1)

    scores = scores.fillna(0)
    return scores.reindex(candidate_movie_ids, fill_value=0.0)
