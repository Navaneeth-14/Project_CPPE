"""
Movie chatbot — RAG-lite approach.

No vector DB needed at this scale. We filter the in-memory movie catalogue
by keywords/genres extracted from the user's message, stuff relevant movie
context into the prompt, and let Groq answer.
"""

from __future__ import annotations
import logging
import re
import pandas as pd

from src.config import GENAI_PROVIDER, GENAI_MODEL, GROQ_API_KEY, OPENAI_API_KEY
from src.mood import MOOD_GENRES

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MAX_CONTEXT_MOVIES = 20   # max movies injected into the prompt
MAX_HISTORY_TURNS  = 6    # how many prior messages to keep in context


# ── Movie context retrieval ───────────────────────────────────────────────────

def _find_relevant_movies(
    message: str,
    movies_df: pd.DataFrame,
    max_results: int = MAX_CONTEXT_MOVIES,
) -> pd.DataFrame:
    """
    Lightweight keyword search over movie titles and genres.
    Returns a small DataFrame of potentially relevant movies for context.
    """
    msg_lower = message.lower()
    words = set(re.findall(r"\b\w{3,}\b", msg_lower))

    # Genre match: check if any known genre word appears in the message
    all_genres = {g.lower() for genres in MOOD_GENRES.values() for g in genres}
    genre_hits = words & all_genres

    scores = pd.Series(0, index=movies_df.index, dtype=float)

    # Title keyword match
    for word in words:
        title_match = movies_df["title"].str.lower().str.contains(word, regex=False)
        scores += title_match.astype(float) * 2.0

    # Genre match
    if genre_hits:
        def genre_score(genre_list):
            if not isinstance(genre_list, list):
                return 0
            return sum(1 for g in genre_list if g.lower() in genre_hits)
        scores += movies_df["genres"].apply(genre_score)

    top = scores.nlargest(max_results)
    return movies_df.loc[top[top > 0].index] if (top > 0).any() else movies_df.sample(min(5, len(movies_df)))


def _build_context(movies: pd.DataFrame) -> str:
    lines = []
    for movie_id, row in movies.iterrows():
        genres = row["genres"] if isinstance(row["genres"], list) else []
        lines.append(f'- "{row["title"]}" (ID {movie_id}) | genres: {", ".join(genres)}')
    return "\n".join(lines)


# ── Prompt ────────────────────────────────────────────────────────────────────

def _build_prompt(
    message: str,
    history: list[dict],
    movie_context: str,
) -> list[dict]:
    system = (
        "You are CineMatch, a friendly movie assistant. "
        "You help users discover movies, answer questions about films, "
        "explain plots, suggest what to watch next, and discuss anything movie-related. "
        "Be warm, conversational, and concise — 2-4 sentences unless the user asks for more. "
        "Only reference movies from the provided catalogue when making recommendations. "
        "If you don't know something specific, say so honestly.\n\n"
        f"Movie catalogue context (relevant titles):\n{movie_context}"
    )

    messages = [{"role": "system", "content": system}]

    # Include recent history (capped to avoid token bloat)
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append(turn)

    messages.append({"role": "user", "content": message})
    return messages


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_llm(messages: list[dict]) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed.")

    if GENAI_PROVIDER == "groq":
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    else:
        client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=GENAI_MODEL,
        messages=messages,
        temperature=0.6,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


# ── Public interface ──────────────────────────────────────────────────────────

def chat(
    message: str,
    history: list[dict],
    movies_df: pd.DataFrame,
) -> str:
    """
    Process one chat turn.

    Args:
        message:   The user's latest message.
        history:   List of prior {"role": "user"|"assistant", "content": "..."} dicts.
        movies_df: The in-memory movie catalogue (for context retrieval).

    Returns:
        The assistant's reply as a plain string.
    """
    relevant = _find_relevant_movies(message, movies_df)
    context  = _build_context(relevant)
    messages = _build_prompt(message, history, context)

    try:
        return _call_llm(messages)
    except Exception as exc:
        logger.error(f"Chatbot LLM call failed: {exc}")
        return "Sorry, I'm having trouble reaching the AI right now. Try again in a moment."
