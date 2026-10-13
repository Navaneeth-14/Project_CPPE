"""
Pre-flight check — run this before starting the server to verify
every layer of the stack is wired correctly.

Usage:
    python scripts/preflight.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"


def check(label, fn):
    print(f"  {label} ...", end=" ", flush=True)
    try:
        result = fn()
        print(f"\033[92mPASS\033[0m" + (f"  {result}" if result else ""))
        return True
    except Exception as e:
        print(f"\033[91mFAIL\033[0m  {e}")
        return False


def main():
    print()
    print("=" * 58)
    print("  CineMatch — Pre-flight Check")
    print("=" * 58)
    results = []

    # ── 1. Config & imports ───────────────────────────────────────
    print("\n[ Module imports ]")

    def chk_config():
        from src.config import (
            MOVIES_FILE, RATINGS_FILE, MOVIES_PARQUET, RATINGS_PARQUET,
            GENRE_MATRIX_FILE, USER_MOVIE_MATRIX_FILE,
            GENAI_PROVIDER, GENAI_MODEL, API_HOST, API_PORT,
        )
        return f"provider={GENAI_PROVIDER}  model={GENAI_MODEL}  server={API_HOST}:{API_PORT}"

    results.append(check("config.py", chk_config))
    results.append(check("storage.py", lambda: __import__("src.storage", fromlist=["storage"])))
    results.append(check("data_pipeline.py", lambda: __import__("src.data_pipeline", fromlist=["x"])))
    results.append(check("content_model.py", lambda: __import__("src.content_model", fromlist=["x"])))
    results.append(check("collaborative_model.py", lambda: __import__("src.collaborative_model", fromlist=["x"])))
    results.append(check("hybrid_recommender.py", lambda: __import__("src.hybrid_recommender", fromlist=["x"])))
    results.append(check("explainer.py", lambda: __import__("src.explainer", fromlist=["x"])))
    results.append(check("app.py (FastAPI)", lambda: __import__("src.app", fromlist=["x"])))

    # ── 2. Raw data files ─────────────────────────────────────────
    print("\n[ Raw data files ]")
    from src.config import MOVIES_FILE, RATINGS_FILE

    def chk_movies_csv():
        assert MOVIES_FILE.exists(), f"Missing: {MOVIES_FILE}"
        import pandas as pd
        df = pd.read_csv(MOVIES_FILE, nrows=3)
        assert list(df.columns) == ["movieId", "title", "genres"]
        return f"{MOVIES_FILE.name} — columns OK"

    def chk_ratings_csv():
        assert RATINGS_FILE.exists(), f"Missing: {RATINGS_FILE}"
        import pandas as pd
        df = pd.read_csv(RATINGS_FILE, nrows=3)
        assert list(df.columns) == ["userId", "movieId", "rating", "timestamp"]
        return f"{RATINGS_FILE.name} — columns OK"

    results.append(check("movies.csv", chk_movies_csv))
    results.append(check("ratings.csv", chk_ratings_csv))

    # ── 3. Processed artifacts ────────────────────────────────────
    print("\n[ Processed artifacts ]")
    from src.config import MOVIES_PARQUET, RATINGS_PARQUET, GENRE_MATRIX_FILE, USER_MOVIE_MATRIX_FILE

    for name, path in [
        ("movies.parquet", MOVIES_PARQUET),
        ("ratings.parquet", RATINGS_PARQUET),
        ("genre_matrix.parquet", GENRE_MATRIX_FILE),
        ("user_movie_matrix.parquet", USER_MOVIE_MATRIX_FILE),
    ]:
        p = path  # capture for lambda
        n = name
        results.append(check(n, lambda p=p, n=n: f"{p.stat().st_size // 1024} KB" if p.exists() else (_ for _ in ()).throw(FileNotFoundError(f"Missing: {p}"))))

    # ── 4. Data load ──────────────────────────────────────────────
    print("\n[ Data loading ]")

    movies_ref = [None]
    ratings_ref = [None]
    genre_ref = [None]
    user_ref = [None]

    def chk_load_data():
        from src.data_pipeline import load_processed
        movies, ratings = load_processed()
        movies_ref[0] = movies
        ratings_ref[0] = ratings
        assert len(movies) > 1000, "Too few movies"
        assert len(ratings) > 50000, "Too few ratings"
        return f"{len(movies):,} movies  {len(ratings):,} ratings  {ratings['userId'].nunique():,} users"

    def chk_load_genre_matrix():
        from src.content_model import load_genre_matrix
        gm = load_genre_matrix()
        genre_ref[0] = gm
        assert gm.shape[0] > 1000, "Genre matrix too small"
        return f"shape {gm.shape}"

    def chk_load_user_matrix():
        from src.collaborative_model import load_user_movie_matrix
        um = load_user_movie_matrix()
        user_ref[0] = um
        assert um.shape[0] > 100, "User matrix too small"
        return f"shape {um.shape}"

    results.append(check("load movies + ratings", chk_load_data))
    results.append(check("load genre matrix", chk_load_genre_matrix))
    results.append(check("load user-movie matrix", chk_load_user_matrix))

    # ── 5. Recommender logic ──────────────────────────────────────
    print("\n[ Recommender logic ]")

    def chk_content_scores():
        from src.content_model import get_content_scores
        gm = genre_ref[0]
        if gm is None:
            raise RuntimeError("Genre matrix not loaded")
        ids = gm.index.tolist()
        scores = get_content_scores(ids[10:30], ids[:10], gm)
        assert (scores >= 0).all() and (scores <= 1).all(), "Scores out of [0,1]"
        return f"20 candidates scored, range [{scores.min():.3f}, {scores.max():.3f}]"

    def chk_collab_scores():
        from src.collaborative_model import get_collaborative_scores
        um = user_ref[0]
        if um is None:
            raise RuntimeError("User matrix not loaded")
        uid = um.index[0]
        candidates = um.columns.tolist()[:20]
        scores = get_collaborative_scores(uid, candidates, um)
        assert len(scores) == 20
        return f"user {uid}: 20 candidates scored"

    def chk_hybrid_user1():
        from src.hybrid_recommender import recommend
        recs = recommend(1, movies_ref[0], ratings_ref[0], genre_ref[0], user_ref[0], top_n=5)
        assert len(recs) == 5
        titles = [r["title"] for r in recs]
        return f"user 1 top pick: \"{recs[0]['title']}\" ({recs[0]['hybrid_score']})"

    def chk_hybrid_user42():
        from src.hybrid_recommender import recommend
        recs = recommend(42, movies_ref[0], ratings_ref[0], genre_ref[0], user_ref[0], top_n=5)
        assert len(recs) == 5
        return f"user 42 top pick: \"{recs[0]['title']}\" ({recs[0]['hybrid_score']})"

    def chk_unknown_user():
        from src.hybrid_recommender import recommend
        recs = recommend(99999, movies_ref[0], ratings_ref[0], genre_ref[0], user_ref[0], top_n=5)
        assert recs == [], "Expected empty list for unknown user"
        return "unknown user correctly returns []"

    results.append(check("content scores [0,1]", chk_content_scores))
    results.append(check("collab scores", chk_collab_scores))
    results.append(check("hybrid recs — user 1", chk_hybrid_user1))
    results.append(check("hybrid recs — user 42", chk_hybrid_user42))
    results.append(check("unknown user safe", chk_unknown_user))

    # ── 6. Explainer fallback ─────────────────────────────────────
    print("\n[ Explainer ]")

    def chk_explainer_fallback():
        from src.hybrid_recommender import recommend
        from src.explainer import explain_recommendations
        recs = recommend(1, movies_ref[0], ratings_ref[0], genre_ref[0], user_ref[0], top_n=3)
        enriched = explain_recommendations(1, recs)
        assert len(enriched) == 3
        assert all("explanation" in r for r in enriched)
        assert all(len(r["explanation"]) > 10 for r in enriched)
        return "3 recs got explanations (fallback or live)"

    results.append(check("explanation attached to every rec", chk_explainer_fallback))

    # ── 7. FastAPI app sanity ─────────────────────────────────────
    print("\n[ FastAPI app ]")

    def chk_routes():
        from src.app import app
        routes = [r.path for r in app.routes]
        assert "/recommend" in routes, "/recommend missing"
        assert "/health" in routes, "/health missing"
        assert "/stats" in routes, "/stats missing"
        assert "/" in routes, "/ (frontend) missing"
        return f"{len(routes)} routes registered"

    def chk_frontend_file():
        from src.config import PROJECT_ROOT
        index = PROJECT_ROOT / "frontend" / "index.html"
        assert index.exists(), f"frontend/index.html not found at {index}"
        size = index.stat().st_size
        assert size > 5000, "index.html looks too small"
        return f"index.html  {size // 1024} KB"

    results.append(check("all routes registered", chk_routes))
    results.append(check("frontend/index.html exists", chk_frontend_file))

    # ── Summary ───────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    print()
    print("=" * 58)
    if passed == total:
        print(f"\033[92m  All {total} checks passed. You're good to go.\033[0m")
        print()
        print("  Start the server:")
        print("    uvicorn src.app:app --reload")
        print()
        print("  Then open:")
        print("    http://127.0.0.1:8000          <- dashboard")
        print("    http://127.0.0.1:8000/docs     <- API explorer")
    else:
        failed = total - passed
        print(f"\033[91m  {failed}/{total} checks failed. Fix the issues above before starting.\033[0m")
    print("=" * 58)
    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
