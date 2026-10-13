# Movie Recommendation & Rating Analysis System

A hybrid movie recommender combining genre-based content filtering and user-based collaborative filtering, served via FastAPI with GenAI-powered explanations.

---

## Architecture

```
src/
├── config.py              # All env/config values in one place
├── storage.py             # Storage abstraction (filesystem now, S3 later)
├── data_pipeline.py       # Ingest → Clean → Validate → Save
├── content_model.py       # TF-IDF genre similarity
├── collaborative_model.py # User-user cosine similarity on rating matrix
├── hybrid_recommender.py  # Blends both signals into final ranking
├── explainer.py           # GenAI explanation call (OpenAI or Anthropic)
└── app.py                 # FastAPI routes (thin — no business logic)
```

---

## Setup

### 1. Install dependencies

```bash
cd movie-recommender
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set your GROQ_API_KEY (free at https://console.groq.com)
# Default provider is Groq with llama-3.1-8b-instant
# Switch GENAI_PROVIDER to "openai" or "anthropic" if preferred
```

### 3. Run the data pipeline

This loads the raw CSVs, cleans them, and builds the genre + user-movie matrices.
Run once (or whenever raw data changes).

```bash
python scripts/run_pipeline.py
```

### 4. Start the API

```bash
uvicorn src.app:app --reload
```

Open **http://127.0.0.1:8000** — the dashboard loads automatically.
API docs at **http://127.0.0.1:8000/docs**.

---

## API Endpoints

### `POST /recommend`

Returns a ranked recommendation list. No GenAI calls — safe to test freely.

```bash
curl -X POST http://127.0.0.1:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "top_n": 5}'
```

**Response:**
```json
{
  "user_id": 1,
  "top_n": 5,
  "recommendations": [
    {
      "movieId": 318,
      "title": "Shawshank Redemption, The (1994)",
      "genres": ["Crime", "Drama"],
      "content_score": 0.7823,
      "collab_score": 0.9341,
      "hybrid_score": 0.6733
    },
    ...
  ]
}
```

---

### `GET /recommend/{user_id}/explain?top_n=5`

Same recommendations with GenAI-generated explanations attached.

```bash
curl "http://127.0.0.1:8000/recommend/1/explain?top_n=5"
```

**Response:**
```json
{
  "user_id": 1,
  "top_n": 5,
  "recommendations": [
    {
      "movieId": 318,
      "title": "Shawshank Redemption, The (1994)",
      "genres": ["Crime", "Drama"],
      "content_score": 0.7823,
      "collab_score": 0.9341,
      "hybrid_score": 0.6733,
      "explanation": "This Crime/Drama closely matches the genres you've enjoyed. It also has a very strong endorsement from users who share your taste — they rated it highly."
    },
    ...
  ]
}
```

---

### `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## GenAI Provider

The explainer supports three providers, configured via `GENAI_PROVIDER` in `.env`:

| Provider | Key env var | Good default model |
|----------|-------------|-------------------|
| `groq` (default) | `GROQ_API_KEY` | `llama-3.1-8b-instant` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-haiku-20240307` |

Groq is recommended for local dev — it's free tier, very fast, and uses the same OpenAI SDK (no extra package). Get a key at [console.groq.com](https://console.groq.com).

---

## Hybrid Scoring

The final score blends two signals:

| Signal | Weight | How it works |
|--------|--------|--------------|
| Content (genre) | 40% | TF-IDF vectors on genres → cosine similarity to user's rated movies |
| Collaborative | 60% | Mean-centered user-movie matrix → weighted average of top-30 similar users |

Weights are tunable via `CONTENT_WEIGHT` / `COLLAB_WEIGHT` in `src/config.py`.

---

## AWS Migration Path

The project is structured for easy migration:

| Component | Local | AWS |
|-----------|-------|-----|
| `storage.py` | Filesystem (parquet) | Replace with boto3/S3 |
| `app.py` routes | uvicorn | Individual Lambda handlers |
| `scripts/run_pipeline.py` | Manual script | Step Functions |
| `.env` | Local file | SSM Parameter Store / Secrets Manager |
| DuckDB queries | Local | Amazon Athena (same SQL) |

Only `storage.py` needs code changes. Everything else just gets rewired.
