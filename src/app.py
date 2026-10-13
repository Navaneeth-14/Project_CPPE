"""
FastAPI application — route definitions only.
No model logic, no data cleaning, no GenAI calls here.
Each route is thin: validate input → call src/ module → return response.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src import content_model, collaborative_model, hybrid_recommender, explainer
from src import mood as mood_module
from src import chatbot, auth, user_profile
from src.data_pipeline import load_processed
from src.config import DEFAULT_TOP_N

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)


# ── App state ─────────────────────────────────────────────────────────────────

class AppState:
    movies_df = None
    ratings_df = None
    genre_matrix = None
    user_movie_matrix = None

state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading processed data and model artifacts...")
    state.movies_df, state.ratings_df = load_processed()
    state.genre_matrix    = content_model.load_genre_matrix()
    state.user_movie_matrix = collaborative_model.load_user_movie_matrix()
    auth.init_db()
    logger.info("Ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="CineMatch API",
    description="Hybrid movie recommender with mood filtering, chatbot, and user accounts.",
    version="2.0.0",
    lifespan=lifespan,
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ── Pydantic models ───────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    top_n: int   = Field(DEFAULT_TOP_N, ge=1, le=50)

class MoodRecommendRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    mood: str    = Field(..., description="One of the mood keys from GET /moods")
    top_n: int   = Field(DEFAULT_TOP_N, ge=1, le=50)

class ChatRequest(BaseModel):
    message: str              = Field(..., min_length=1, max_length=500)
    history: list[dict]       = Field(default_factory=list)

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=40)
    email: str    = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    username: str
    password: str

class GenreOnboardRequest(BaseModel):
    genres: list[str] = Field(..., min_length=1, max_length=10)

class MovieRecommendation(BaseModel):
    movieId: int
    title: str
    genres: list[str]
    content_score: float
    collab_score: float
    hybrid_score: float

class MoodRecommendation(MovieRecommendation):
    mood_match: bool

class MovieExplanation(MovieRecommendation):
    explanation: str

class RecommendResponse(BaseModel):
    user_id: int
    top_n: int
    recommendations: list[MovieRecommendation]

class ExplainResponse(BaseModel):
    user_id: int
    top_n: int
    recommendations: list[MovieExplanation]

class MoodRecommendResponse(BaseModel):
    user_id: int
    mood: str
    top_n: int
    recommendations: list[MoodRecommendation]

class ChatResponse(BaseModel):
    reply: str

class AuthResponse(BaseModel):
    token: str
    user: dict

class ProfileRecommendResponse(BaseModel):
    username: str
    preferred_genres: list[str]
    recommendations: list[MovieRecommendation]


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _get_current_user(authorization: str | None) -> dict:
    """Decode Bearer token from Authorization header. Raises 401 if invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    payload = auth.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token expired or invalid.")
    user = auth.get_user(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


# ── Dataset helpers ───────────────────────────────────────────────────────────

def _check_dataset_user(user_id: int) -> None:
    valid = set(state.ratings_df["userId"].unique())
    if user_id not in valid:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found in dataset. Valid range: 1–{max(valid)}.",
        )

def _get_recs(user_id: int, top_n: int) -> list[dict]:
    recs = hybrid_recommender.recommend(
        user_id=user_id,
        movies_df=state.movies_df,
        ratings_df=state.ratings_df,
        genre_matrix=state.genre_matrix,
        user_movie_matrix=state.user_movie_matrix,
        top_n=top_n,
    )
    if not recs:
        raise HTTPException(status_code=404, detail=f"No recommendations for user {user_id}.")
    return recs


# ════════════════════════════════════════════════════════════════════════════
# Routes — Recommendations (existing, unchanged)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/recommend", response_model=RecommendResponse, tags=["Recommendations"])
def post_recommend(body: RecommendRequest):
    """Ranked recommendations for a dataset user. No GenAI call."""
    _check_dataset_user(body.user_id)
    return RecommendResponse(
        user_id=body.user_id, top_n=body.top_n,
        recommendations=_get_recs(body.user_id, body.top_n),
    )


@app.get("/recommend/{user_id}/explain", response_model=ExplainResponse, tags=["Recommendations"])
def get_explain(user_id: int, top_n: int = DEFAULT_TOP_N):
    """Recommendations + GenAI explanation per movie."""
    if not 1 <= top_n <= 50:
        raise HTTPException(status_code=422, detail="top_n must be 1–50.")
    _check_dataset_user(user_id)
    recs = _get_recs(user_id, top_n)
    enriched = explainer.explain_recommendations(user_id=user_id, recommendations=recs)
    return ExplainResponse(user_id=user_id, top_n=top_n, recommendations=enriched)


# ════════════════════════════════════════════════════════════════════════════
# Routes — Mood
# ════════════════════════════════════════════════════════════════════════════

@app.get("/moods", tags=["Mood"])
def get_moods():
    """List all available mood options."""
    return mood_module.list_moods()


@app.post("/recommend/mood", response_model=MoodRecommendResponse, tags=["Mood"])
def post_mood_recommend(body: MoodRecommendRequest):
    """Recommendations filtered and re-ranked by mood."""
    _check_dataset_user(body.user_id)
    if body.mood not in mood_module.MOOD_GENRES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown mood '{body.mood}'. Call GET /moods for valid options.",
        )
    # Fetch a larger pool so mood re-ranking has enough to work with
    recs = _get_recs(body.user_id, top_n=min(body.top_n * 4, 50))
    boosted = mood_module.apply_mood_boost(recs, body.mood)
    return MoodRecommendResponse(
        user_id=body.user_id,
        mood=body.mood,
        top_n=body.top_n,
        recommendations=boosted[: body.top_n],
    )


# ════════════════════════════════════════════════════════════════════════════
# Routes — Chatbot
# ════════════════════════════════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse, tags=["Chatbot"])
def post_chat(body: ChatRequest):
    """
    Send a message to the movie chatbot.
    Pass the conversation history from the client to maintain context.
    """
    reply = chatbot.chat(
        message=body.message,
        history=body.history,
        movies_df=state.movies_df,
    )
    return ChatResponse(reply=reply)


# ════════════════════════════════════════════════════════════════════════════
# Routes — Auth & User Accounts
# ════════════════════════════════════════════════════════════════════════════

@app.post("/auth/signup", response_model=AuthResponse, tags=["Auth"])
def post_signup(body: SignupRequest):
    """Create a new account."""
    try:
        user = auth.signup(body.username, body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = auth.create_token(user["id"], user["username"])
    return AuthResponse(token=token, user=user)


@app.post("/auth/login", response_model=AuthResponse, tags=["Auth"])
def post_login(body: LoginRequest):
    """Login and receive a JWT token."""
    try:
        user = auth.login(body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    token = auth.create_token(user["id"], user["username"])
    return AuthResponse(token=token, user=user)


@app.post("/me/genres", tags=["Auth"])
def post_genres(body: GenreOnboardRequest, authorization: str = Header(None)):
    """Save genre preferences for the logged-in user."""
    user = _get_current_user(authorization)
    valid = set(user_profile.ALL_GENRES)
    bad = [g for g in body.genres if g not in valid]
    if bad:
        raise HTTPException(status_code=422, detail=f"Unknown genres: {bad}. Valid: {sorted(valid)}")
    auth.save_genres(user["id"], body.genres)
    return {"saved": body.genres}


@app.get("/me/genres", tags=["Auth"])
def get_my_genres(authorization: str = Header(None)):
    """Get the logged-in user's saved genre preferences."""
    user = _get_current_user(authorization)
    return {"genres": auth.get_genres(user["id"])}


@app.get("/me/recommend", response_model=ProfileRecommendResponse, tags=["Auth"])
def get_my_recommendations(top_n: int = DEFAULT_TOP_N, authorization: str = Header(None)):
    """
    Personalized recommendations for the logged-in user based on their
    saved genre preferences (cold-start content-based).
    """
    if not 1 <= top_n <= 50:
        raise HTTPException(status_code=422, detail="top_n must be 1–50.")
    user = _get_current_user(authorization)
    genres = auth.get_genres(user["id"])
    if not genres:
        raise HTTPException(
            status_code=400,
            detail="No genre preferences saved. Call POST /me/genres first.",
        )
    recs = user_profile.recommend_for_new_user(
        preferred_genres=genres,
        movies_df=state.movies_df,
        genre_matrix=state.genre_matrix,
        top_n=top_n,
    )
    return ProfileRecommendResponse(
        username=user["username"],
        preferred_genres=genres,
        recommendations=recs,
    )


@app.get("/genres", tags=["Auth"])
def get_all_genres():
    """List all genres available for onboarding."""
    return {"genres": sorted(user_profile.ALL_GENRES)}


# ════════════════════════════════════════════════════════════════════════════
# Routes — Utility
# ════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Utility"])
def health():
    return {"status": "ok", "movies_loaded": state.movies_df is not None}


@app.get("/stats", tags=["Utility"])
def stats():
    return {
        "total_movies":  int(len(state.movies_df)),
        "total_ratings": int(len(state.ratings_df)),
        "active_users":  int(state.ratings_df["userId"].nunique()),
    }


@app.get("/", include_in_schema=False)
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return {"message": "Frontend not found."}
    return FileResponse(index)
