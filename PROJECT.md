# CineMatch — Project Documentation

---

## What Is This?

CineMatch is a hybrid movie recommendation system built locally in Python.
It analyses 10,322 movies and 105,332 real ratings from 668 users (MovieLens dataset)
and recommends movies a user would likely enjoy — with AI-written explanations for each pick.

---

## What We Built (Phase 1 — Local)

### The Recommender Engine

The system uses **two independent signals** blended into one score:

**1. Content-Based (Genre Similarity — 40% weight)**
Every movie's genres are converted into a TF-IDF vector (a mathematical fingerprint).
The user's taste profile is built from genres of movies they've already rated.
Each candidate movie is scored by how closely its genre mix matches that profile.

**2. Collaborative Filtering (Community Signal — 60% weight)**
All 668 users' ratings form a matrix. The top 30 users most similar to the target user
are identified by cosine similarity. Their ratings are used to predict how much the
target user would enjoy unseen movies — regardless of genre.

**Final score:**
```
hybrid_score = (0.4 × content_score) + (0.6 × collab_score)
```

### The Data Pipeline

Raw CSVs → cleaned → validated → saved as Parquet files.
Run once before starting the server. Outputs four artifacts:

- `movies.parquet` — clean movie catalogue
- `ratings.parquet` — clean rating records
- `genre_matrix.parquet` — TF-IDF genre vectors (10,322 × 19)
- `user_movie_matrix.parquet` — mean-centered user ratings (668 × 10,318)

### The API (FastAPI)

Two main endpoints:

| Endpoint | What it does |
|----------|-------------|
| `POST /recommend` | Returns ranked movies with scores. No AI call — fast and free to test. |
| `GET /recommend/{user_id}/explain` | Same results + a 1–2 sentence AI explanation per movie (Groq) |
| `GET /stats` | Dataset stats shown on the dashboard |
| `GET /health` | Server health check |

### The Dashboard (frontend/index.html)

Single-page UI served at `http://127.0.0.1:8000`.

- Enter a user ID (1–668) and how many recommendations you want
- Toggle between **Scores only** (instant) and **✦ AI explain** (calls Groq)
- Each card shows: movie title, genre chips, three score bars (Genre fit / Community / Overall), and optionally an AI insight
- Live dataset stats in the header (movies, ratings, users)

### Project Structure

```
movie-recommender/
├── data/
│   ├── raw/                     # movies.csv, ratings.csv
│   └── processed/               # parquet artifacts (built by pipeline)
├── src/
│   ├── config.py                # all settings and env vars in one place
│   ├── storage.py               # file read/write abstraction (→ S3 later)
│   ├── data_pipeline.py         # ingest → clean → validate → save
│   ├── content_model.py         # TF-IDF genre similarity
│   ├── collaborative_model.py   # user-user cosine similarity
│   ├── hybrid_recommender.py    # blends both signals
│   ├── explainer.py             # Groq API call + structured prompt
│   └── app.py                   # FastAPI routes (thin, no logic)
├── frontend/
│   └── index.html               # dashboard (zero dependencies)
├── scripts/
│   ├── run_pipeline.py          # builds data artifacts (run once)
│   └── preflight.py             # checks everything works before starting
├── tests/
│   └── test_pipeline.py         # 9 sanity tests
├── .env                         # your API keys and config (never commit)
├── .env.example                 # template for .env
├── requirements.txt
└── README.md
```

### Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Data processing | pandas + pyarrow | Right size for this dataset, no Spark needed |
| Similarity math | scikit-learn (TF-IDF, cosine) | Clean, well-tested, no deep learning overkill |
| API | FastAPI + uvicorn | Fast, async, auto-generates docs |
| AI explanations | Groq (llama / gpt-oss) | Free tier, 1000 tokens/sec, OpenAI-compatible |
| Config | python-dotenv | One .env, no hardcoded values anywhere |

---

## How to Run It

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up .env (copy example, add your Groq key from console.groq.com)
cp .env.example .env

# 3. Build data pipeline (once)
python scripts/run_pipeline.py

# 4. Check everything is wired correctly
python scripts/preflight.py

# 5. Start the server
uvicorn src.app:app --reload

# Open http://127.0.0.1:8000
```

---

## Current User Flow (Phase 1)

```
You open http://127.0.0.1:8000
        │
        ▼
Enter a User ID (1–668) + how many recommendations
        │
        ├── Scores only mode
        │   └── See ranked movies with Genre fit / Community / Overall bars
        │
        └── AI explain mode
            └── Same movies + one sentence per movie explaining why it was picked
```

**Limitation:** The 668 user IDs are fixed from the MovieLens dataset.
You can't create your own account or provide your own preferences yet.
That's Phase 2.

---

## AWS Migration Readiness

The code is shaped so Phase 2 migration is a rewire, not a rewrite:

| What | Today | AWS (Phase 2) |
|------|-------|---------------|
| File storage | Local filesystem | `storage.py` → boto3/S3 |
| API routes | uvicorn | Each route → Lambda handler |
| Pipeline | `run_pipeline.py` | Step Functions |
| Config/secrets | `.env` | SSM Parameter Store |
| SQL queries | DuckDB | Amazon Athena (same SQL) |

Only `storage.py` needs code changes. Everything else gets rewired.

---

## Phase 2 — The Vision (Not Built Yet)

This is what Phase 2 should look like as a real product.

---

### Feature 1 — User Accounts & Genre Onboarding

**What it is:**
Real signup/login. When a new user joins, the app asks which genres they enjoy
(Action, Comedy, Horror, etc.) and uses those selections as a starter profile.

**Why it matters:**
Right now the system needs existing rating history to work. New users have none —
this is the classic "cold start problem". Genre onboarding solves it by creating
a synthetic taste profile from day one.

**What it needs to build:**
- User database (SQLite locally, PostgreSQL/DynamoDB on AWS)
- Auth layer (JWT tokens — simple, stateless, Lambda-friendly)
- Preference storage (genre selections stored per user)
- Cold-start logic in the recommender: when a user has < N ratings,
  fall back to genre-weighted content scoring instead of collaborative

**Flow:**
```
Sign up → pick 3–5 genres you like → get recommendations immediately
```

---

### Feature 2 — Behavioral Learning (Taste Profile Over Time)

**What it is:**
Every interaction — clicking a recommendation, skipping it, rating it —
gets stored. The more you use it, the more accurately it knows your taste.

**Why it matters:**
This is what separates a real recommender from a one-shot query.
Netflix and Spotify do exactly this: every scroll, pause, and skip is a signal.

**What it needs to build:**
- Interaction event store (click / skip / rate / watch)
- A per-user event log that feeds back into the recommendation model
- Incremental model update: recompute a user's profile after N new interactions
  (not full retrain — just update their row in the matrices)

**Signals to capture:**
| Action | Signal strength |
|--------|----------------|
| Explicit rating (1–5 stars) | Strongest |
| Clicked / viewed details | Medium |
| Skipped without clicking | Weak negative |
| Watched (if connected to a service) | Strong |

---

### Feature 3 — Mood-Based Recommendations

**What it is:**
Before getting recommendations, the user picks their mood for tonight.
The system filters and re-weights candidates based on that mood.

**Why it matters:**
A person who loved Inception might want a lighthearted comedy tonight.
Genre history alone doesn't capture present intent. Mood does.

**What it needs to build:**
- A mood → genre cluster mapping (defined once, tunable)
- A mood selector UI step before the recommend call
- A filter/boost layer in `hybrid_recommender.py` that adjusts candidate scoring
  based on the active mood

**Mood to genre mapping (example):**
| Mood | Boosted genres |
|------|---------------|
| Something light | Comedy, Animation, Romance |
| Intense / gripping | Thriller, Crime, Mystery |
| Mind-bending | Sci-Fi, Mystery, Drama |
| Feel-good | Comedy, Adventure, Family |
| Emotional / deep | Drama, Romance |
| Action-packed | Action, Adventure, War |

---

### Feature 4 — Movie Chatbot

**What it is:**
A chat interface where you can ask anything about movies:
- "What is Inception about?"
- "Is Parasite suitable for kids?"
- "Recommend something like Interstellar but shorter"
- "What did critics say about The Godfather?"

**Why it matters:**
Recommendations solve "what should I watch". The chatbot solves "help me decide"
and "tell me more" — a different but complementary need.

**What it needs to build:**
- Movie metadata embedded into a vector store (ChromaDB locally, Pinecone on AWS)
- A RAG (Retrieval Augmented Generation) pipeline:
  user question → find relevant movie docs → pass to Groq with context → answer
- A chat UI component on the dashboard (persistent session, message history)
- Groq is already wired in — it just needs the retrieval layer added

**Example interaction:**
```
User: "I liked Arrival, what should I watch next?"
Bot:  "Based on your taste for cerebral Sci-Fi, you'd likely enjoy
       Annihilation (2018) — same meditative pacing and unreliable
       reality theme — and Coherence (2013), a low-budget but
       mind-bending choice highly rated by users similar to you."
```

---

## Summary — What's Done vs What's Next

| Feature | Status |
|---------|--------|
| Hybrid recommender engine (content + collab) | ✅ Built |
| Data pipeline (clean, validated, Parquet) | ✅ Built |
| FastAPI with 18 endpoints | ✅ Built |
| AI explanations via Groq | ✅ Built |
| Dashboard UI with 4 panels | ✅ Built |
| Pre-flight check script | ✅ Built |
| AWS migration-ready architecture | ✅ Built |
| **Mood-based filtering** | ✅ **Phase 2 complete** |
| **Movie chatbot (RAG)** | ✅ **Phase 2 complete** |
| **User accounts + auth** | ✅ **Phase 2 complete** |
| **Genre onboarding (cold start)** | ✅ **Phase 2 complete** |
| Behavioral learning (feedback loop) | 🔲 Deferred (Phase 3) |
