"""
Auth layer — signup, login, JWT token management.
Uses SQLite locally (one file, zero infra). Swap to RDS/DynamoDB on AWS.
"""

from __future__ import annotations
import sqlite3
import hashlib
import hmac
import os
import time
import json
import base64
import logging
from pathlib import Path

from src.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "users.db"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days


# ── DB bootstrap ──────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                email       TEXT    NOT NULL UNIQUE,
                password_hash TEXT  NOT NULL,
                created_at  INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_genres (
                user_id     INTEGER NOT NULL REFERENCES users(id),
                genre       TEXT    NOT NULL,
                PRIMARY KEY (user_id, genre)
            );
        """)
    logger.info("User DB initialised.")


# ── Password hashing ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}${h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return hmac.compare_digest(check.hex(), h)
    except Exception:
        return False


# ── JWT (minimal, no external lib) ───────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign(payload: dict) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body   = _b64(json.dumps(payload).encode())
    sig    = _b64(
        hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"


def _verify_token(token: str) -> dict | None:
    try:
        header, body, sig = token.split(".")
        expected = _b64(
            hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        padding = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + padding))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def create_token(user_id: int, username: str) -> str:
    return _sign({"sub": user_id, "username": username, "exp": int(time.time()) + TOKEN_TTL})


def decode_token(token: str) -> dict | None:
    return _verify_token(token)


# ── User operations ───────────────────────────────────────────────────────────

class AuthError(Exception):
    pass


def signup(username: str, email: str, password: str) -> dict:
    """Create a new user. Returns user dict on success, raises AuthError on conflict."""
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    pw_hash = _hash_password(password)
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
                (username.strip(), email.strip().lower(), pw_hash, int(time.time())),
            )
            user_id = cur.lastrowid
        logger.info(f"New user signed up: {username} (id={user_id})")
        return {"id": user_id, "username": username, "email": email}
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise AuthError("Username already taken.")
        raise AuthError("Email already registered.")


def login(username: str, password: str) -> dict:
    """Verify credentials. Returns user dict on success, raises AuthError on failure."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        raise AuthError("Invalid username or password.")
    return {"id": row["id"], "username": row["username"], "email": row["email"]}


def get_user(user_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── Genre preferences ─────────────────────────────────────────────────────────

def save_genres(user_id: int, genres: list[str]) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM user_genres WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO user_genres (user_id, genre) VALUES (?,?)",
            [(user_id, g) for g in genres],
        )


def get_genres(user_id: int) -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT genre FROM user_genres WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [r["genre"] for r in rows]
