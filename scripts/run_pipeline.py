"""
One-off script: run the full data pipeline and build all model artifacts.
Run this once before starting the API server.

Usage:
    python scripts/run_pipeline.py
"""

import sys
import logging
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 55)
    logger.info("  Movie Recommender — Data Pipeline")
    logger.info("=" * 55)

    # ── Step 1: Data pipeline ─────────────────────────────────────────────────
    from src.data_pipeline import run_pipeline
    movies_df, ratings_df = run_pipeline()

    # ── Step 2: Genre (content) matrix ────────────────────────────────────────
    from src.content_model import build_genre_matrix
    build_genre_matrix(movies_df)

    # ── Step 3: User–movie (collaborative) matrix ─────────────────────────────
    from src.collaborative_model import build_user_movie_matrix
    build_user_movie_matrix(ratings_df)

    logger.info("=" * 55)
    logger.info("  Pipeline complete. You can now start the API:")
    logger.info("  uvicorn src.app:app --reload")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
