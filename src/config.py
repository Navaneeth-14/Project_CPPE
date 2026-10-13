"""
Central configuration. All env vars and path constants live here.
Swap values here (or in .env) when migrating to AWS — nothing else should change.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Data directories ──────────────────────────────────────────────────────────
RAW_DATA_DIR = PROJECT_ROOT / os.getenv("RAW_DATA_DIR", "data/raw")
PROCESSED_DATA_DIR = PROJECT_ROOT / os.getenv("PROCESSED_DATA_DIR", "data/processed")

# Raw source files
MOVIES_FILE = RAW_DATA_DIR / "movies.csv"
RATINGS_FILE = RAW_DATA_DIR / "ratings.csv"

# Processed artifacts
MOVIES_PARQUET = PROCESSED_DATA_DIR / "movies.parquet"
RATINGS_PARQUET = PROCESSED_DATA_DIR / "ratings.parquet"
GENRE_MATRIX_FILE = PROCESSED_DATA_DIR / "genre_matrix.parquet"
USER_MOVIE_MATRIX_FILE = PROCESSED_DATA_DIR / "user_movie_matrix.parquet"

# ── GenAI ─────────────────────────────────────────────────────────────────────
GENAI_PROVIDER = os.getenv("GENAI_PROVIDER", "groq")  # "groq" | "openai" | "anthropic"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GENAI_MODEL = os.getenv("GENAI_MODEL", "llama-3.1-8b-instant")  # default: fast free Groq model

# ── API server ────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")

# ── Recommender defaults ──────────────────────────────────────────────────────
DEFAULT_TOP_N = 10
CONTENT_WEIGHT = 0.4       # weight for genre-based score in hybrid blend
COLLAB_WEIGHT = 0.6        # weight for collaborative score in hybrid blend
MIN_RATINGS_PER_USER = 5   # users with fewer ratings are excluded from collab model
