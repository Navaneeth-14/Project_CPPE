"""
Data pipeline: load → clean → validate → save processed artifacts.

Each step is a standalone callable function so they can later be wired
into Step Functions or sequential Lambda calls without restructuring.
"""

import logging
import pandas as pd
from src import storage
from src.config import (
    MOVIES_FILE, RATINGS_FILE,
    MOVIES_PARQUET, RATINGS_PARQUET,
    MIN_RATINGS_PER_USER,
)

logger = logging.getLogger(__name__)


# ── Step 1: Ingest ────────────────────────────────────────────────────────────

def ingest_movies() -> pd.DataFrame:
    """Load movies.csv, parse pipe-separated genres into a list."""
    logger.info("Ingesting movies...")
    df = storage.read_csv(MOVIES_FILE)
    df.columns = df.columns.str.strip()
    df["genres"] = df["genres"].str.split("|")
    # Drop rows with no valid genres
    df = df[df["genres"].apply(lambda g: g != ["(no genres listed)"])]
    logger.info(f"  Loaded {len(df):,} movies")
    return df


def ingest_ratings() -> pd.DataFrame:
    """Load ratings.csv, parse timestamp to datetime."""
    logger.info("Ingesting ratings...")
    df = storage.read_csv(RATINGS_FILE)
    df.columns = df.columns.str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    logger.info(f"  Loaded {len(df):,} ratings")
    return df


# ── Step 2: Clean ─────────────────────────────────────────────────────────────

def clean_movies(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate and validate movie data."""
    before = len(df)
    df = df.drop_duplicates(subset="movieId")
    df = df.dropna(subset=["movieId", "title"])
    df["movieId"] = df["movieId"].astype(int)
    logger.info(f"  Movies cleaned: {before:,} → {len(df):,}")
    return df.reset_index(drop=True)


def clean_ratings(df: pd.DataFrame, movies_df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicates, out-of-range ratings, and ratings for unknown movies.
    Also filter out users with too few ratings to participate in collab model.
    """
    before = len(df)
    df = df.drop_duplicates(subset=["userId", "movieId"])
    df = df[df["rating"].between(0.5, 5.0)]
    valid_movie_ids = set(movies_df["movieId"].unique())
    df = df[df["movieId"].isin(valid_movie_ids)]

    # Drop low-activity users
    counts = df.groupby("userId")["movieId"].count()
    active_users = counts[counts >= MIN_RATINGS_PER_USER].index
    df = df[df["userId"].isin(active_users)]

    logger.info(f"  Ratings cleaned: {before:,} → {len(df):,}")
    return df.reset_index(drop=True)


# ── Step 3: Validate ──────────────────────────────────────────────────────────

def validate(movies_df: pd.DataFrame, ratings_df: pd.DataFrame) -> None:
    """Basic sanity checks — raise ValueError on bad data."""
    assert "movieId" in movies_df.columns and "genres" in movies_df.columns
    assert "userId" in ratings_df.columns and "rating" in ratings_df.columns
    assert ratings_df["rating"].between(0.5, 5.0).all(), "Rating out of range"
    overlap = set(ratings_df["movieId"]).intersection(set(movies_df["movieId"]))
    assert len(overlap) > 0, "No overlap between ratings and movies"
    logger.info(
        f"  Validation passed — {len(movies_df):,} movies, "
        f"{len(ratings_df):,} ratings, "
        f"{ratings_df['userId'].nunique():,} active users"
    )


# ── Step 4: Save ──────────────────────────────────────────────────────────────

def save_processed(movies_df: pd.DataFrame, ratings_df: pd.DataFrame) -> None:
    """Persist cleaned DataFrames as Parquet."""
    storage.save_dataframe(movies_df.set_index("movieId"), MOVIES_PARQUET)
    storage.save_dataframe(ratings_df, RATINGS_PARQUET)
    logger.info(f"  Saved processed data to {MOVIES_PARQUET.parent}")


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_pipeline() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run the full ingest → clean → validate → save pipeline.
    Returns (movies_df, ratings_df) with movieId as index on movies_df.
    """
    movies_raw = ingest_movies()
    ratings_raw = ingest_ratings()

    movies = clean_movies(movies_raw)
    ratings = clean_ratings(ratings_raw, movies)

    validate(movies, ratings)
    save_processed(movies, ratings)

    return movies.set_index("movieId"), ratings


def load_processed() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load already-processed artifacts from disk."""
    movies = storage.load_dataframe(MOVIES_PARQUET)
    ratings = storage.load_dataframe(RATINGS_PARQUET)
    return movies, ratings
