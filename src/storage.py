"""
Storage abstraction layer.

All reads and writes to data files go through here.
Locally: plain filesystem with pandas/parquet.
AWS phase: replace function bodies to use boto3/S3 — nothing else changes.
"""

from pathlib import Path
import pandas as pd
from src.config import PROCESSED_DATA_DIR


def ensure_dirs() -> None:
    """Create processed data directory if it doesn't exist."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Persist a DataFrame as Parquet."""
    ensure_dirs()
    df.to_parquet(path, index=True)


def load_dataframe(path: Path) -> pd.DataFrame:
    """Load a Parquet file into a DataFrame. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Processed file not found: {path}\n"
            "Run `python scripts/run_pipeline.py` to build the data pipeline first."
        )
    return pd.read_parquet(path)


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    """Read a raw CSV file."""
    if not path.exists():
        raise FileNotFoundError(f"Raw data file not found: {path}")
    return pd.read_csv(path, **kwargs)


def artifact_exists(path: Path) -> bool:
    """Check whether a processed artifact is already on disk."""
    return path.exists()
