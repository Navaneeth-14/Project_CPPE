"""
Sanity tests for the data pipeline and recommender core.
Run with: pytest tests/
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_pipeline import ingest_movies, ingest_ratings, clean_movies, clean_ratings, validate
from src.content_model import get_content_scores
from src.collaborative_model import get_collaborative_scores


# ── Pipeline tests ────────────────────────────────────────────────────────────

def test_ingest_movies_shape():
    df = ingest_movies()
    assert "movieId" in df.columns
    assert "genres" in df.columns
    assert len(df) > 1000


def test_ingest_movies_genres_are_lists():
    df = ingest_movies()
    assert all(isinstance(g, list) for g in df["genres"].head(20))


def test_ingest_ratings_shape():
    df = ingest_ratings()
    assert "userId" in df.columns
    assert "rating" in df.columns
    assert len(df) > 50_000


def test_clean_movies_no_duplicates():
    df = ingest_movies()
    cleaned = clean_movies(df)
    assert cleaned["movieId"].nunique() == len(cleaned)


def test_clean_ratings_range():
    movies = clean_movies(ingest_movies())
    ratings = ingest_ratings()
    cleaned = clean_ratings(ratings, movies)
    assert cleaned["rating"].between(0.5, 5.0).all()


def test_validate_passes():
    movies = clean_movies(ingest_movies())
    ratings = clean_ratings(ingest_ratings(), movies)
    # Should not raise
    validate(movies, ratings)


# ── Content model tests ───────────────────────────────────────────────────────

def test_content_scores_range():
    """Content scores should be in [0, 1]."""
    movies = clean_movies(ingest_movies()).set_index("movieId")
    from src.content_model import build_genre_matrix
    genre_matrix = build_genre_matrix(movies)

    # Use first 5 movies as rated, score next 20
    all_ids = genre_matrix.index.tolist()
    rated = all_ids[:5]
    candidates = all_ids[5:25]

    scores = get_content_scores(candidates, rated, genre_matrix)
    assert (scores >= 0).all() and (scores <= 1).all()


# ── Collaborative model tests ─────────────────────────────────────────────────

def test_collab_scores_returns_series():
    """Collaborative scores should be a Series of the right length."""
    movies = clean_movies(ingest_movies()).set_index("movieId")
    ratings = clean_ratings(ingest_ratings(), movies.reset_index())
    from src.collaborative_model import build_user_movie_matrix
    matrix = build_user_movie_matrix(ratings)

    user_id = matrix.index[0]
    candidates = matrix.columns.tolist()[:20]
    scores = get_collaborative_scores(user_id, candidates, matrix)
    assert len(scores) == 20


def test_unknown_user_returns_zeros():
    movies = clean_movies(ingest_movies()).set_index("movieId")
    ratings = clean_ratings(ingest_ratings(), movies.reset_index())
    from src.collaborative_model import build_user_movie_matrix
    matrix = build_user_movie_matrix(ratings)

    scores = get_collaborative_scores(99999, [1, 2, 3], matrix)
    assert (scores == 0).all()
