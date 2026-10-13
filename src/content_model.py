"""
Content-based model: genre similarity between movies using TF-IDF + cosine similarity.

Builds a genre matrix once (saved to disk) and provides fast lookup at query time.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src import storage
from src.config import GENRE_MATRIX_FILE

logger = logging.getLogger(__name__)


# ── Build ─────────────────────────────────────────────────────────────────────

def build_genre_matrix(movies_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute TF-IDF genre vectors for every movie.
    Rows = movieId, columns = genre terms, values = TF-IDF weight.
    Result saved to disk via storage layer.
    """
    logger.info("Building genre TF-IDF matrix...")

    # Join genre list back to space-separated string for TF-IDF
    genre_strings = movies_df["genres"].apply(
        lambda g: " ".join(g) if isinstance(g, list) else str(g)
    )

    vectorizer = TfidfVectorizer(token_pattern=r"[^\s]+")
    tfidf_matrix = vectorizer.fit_transform(genre_strings)

    genre_df = pd.DataFrame(
        tfidf_matrix.toarray(),
        index=movies_df.index,          # movieId index
        columns=vectorizer.get_feature_names_out(),
    )

    storage.save_dataframe(genre_df, GENRE_MATRIX_FILE)
    logger.info(f"  Genre matrix: {genre_df.shape[0]:,} movies × {genre_df.shape[1]} genres")
    return genre_df


def load_genre_matrix() -> pd.DataFrame:
    return storage.load_dataframe(GENRE_MATRIX_FILE)


# ── Query ─────────────────────────────────────────────────────────────────────

def get_content_scores(
    candidate_movie_ids: list[int],
    rated_movie_ids: list[int],
    genre_matrix: pd.DataFrame,
) -> pd.Series:
    """
    For each candidate movie, compute its average cosine similarity to the
    movies a user has already rated (their "taste profile").

    Returns a Series indexed by movieId, values in [0, 1].
    """
    # Filter to movies we have vectors for
    known_ids = set(genre_matrix.index)
    seed_ids = [m for m in rated_movie_ids if m in known_ids]
    cand_ids = [m for m in candidate_movie_ids if m in known_ids]

    if not seed_ids or not cand_ids:
        return pd.Series(0.0, index=candidate_movie_ids)

    seed_vectors = genre_matrix.loc[seed_ids].values        # (S, G)
    cand_vectors = genre_matrix.loc[cand_ids].values        # (C, G)

    # sim shape: (C, S) — for each candidate, similarity to each seed movie
    sim = cosine_similarity(cand_vectors, seed_vectors)     # (C, S)
    avg_sim = sim.mean(axis=1)                               # (C,)

    scores = pd.Series(avg_sim, index=cand_ids)

    # Fill 0 for any candidate not in genre matrix
    return scores.reindex(candidate_movie_ids, fill_value=0.0)


def get_similar_movies(
    movie_id: int,
    genre_matrix: pd.DataFrame,
    top_n: int = 10,
) -> pd.Series:
    """
    Return the top-N movies most similar to a given movie by genre.
    Useful for item-based lookups; not used in the main hybrid path.
    """
    if movie_id not in genre_matrix.index:
        return pd.Series(dtype=float)

    target = genre_matrix.loc[[movie_id]].values
    all_vectors = genre_matrix.values
    sims = cosine_similarity(target, all_vectors).flatten()

    result = pd.Series(sims, index=genre_matrix.index).drop(movie_id)
    return result.nlargest(top_n)
