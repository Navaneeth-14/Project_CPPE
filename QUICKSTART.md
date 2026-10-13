# CineMatch — Quick Start Guide

**Get up and running in under 2 minutes.**

---

## Prerequisites

- Python 3.10+ installed
- Groq API key (free at [console.groq.com](https://console.groq.com))

---

## Setup (First Time Only)

```bash
# 1. Navigate to project
cd "e:\Wipro CPPPE\movie-recommender"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key in .env
# Already done if you followed earlier — just verify it's there:
# GROQ_API_KEY=gsk_...

# 4. Build the data pipeline (takes ~10 seconds)
python scripts/run_pipeline.py

# 5. Optional: Run pre-flight check
python scripts/preflight.py
```

---

## Start the Server

```bash
uvicorn src.app:app --reload
```

**Then open:** http://127.0.0.1:8000

---

## What to Try First

### 1. Create Your Account (30 seconds)
- Click the "👤 My Account" tab
- Click "Create account" → pick a username & password
- Select 3-5 genres you enjoy
- Click "Save preferences"
- Click "Get my picks" → see your personalized recommendations

### 2. Explore by Mood (10 seconds)
- Go to "🎭 Mood Pick"
- Click a mood chip (e.g. "🤯 Mind-Bending")
- Enter a dataset user ID (try 1, 42, or 200)
- Click "Find my picks"

### 3. Ask the Chatbot (10 seconds)
- Go to "💬 Ask CineMatch"
- Type: "What's Inception about?"
- Or: "Recommend something like The Matrix"

### 4. Try the Original Recommender
- Go to "🔍 Discover"
- Enter user ID 1, pick "✦ AI explain"
- Click "Recommend"
- See the hybrid scores + AI-generated explanations

---

## The Four Tabs Explained

| Tab | What It Does | Best For |
|-----|-------------|----------|
| 🔍 **Discover** | Original hybrid recommender for dataset users (1–668) | Understanding how the scoring works |
| 🎭 **Mood Pick** | Filter by mood (intense, feel-good, etc.) | "I want something specific tonight" |
| 💬 **Ask CineMatch** | Chat with AI about movies | Questions, recommendations, explanations |
| 👤 **My Account** | Personal profile with genre-based recs | Your own taste, no dataset user needed |

---

## API Endpoints (For Testing / Integration)

### Health & Stats
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/stats
```

### Dataset User Recommendations
```bash
# Plain scores
curl -X POST http://127.0.0.1:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "top_n": 5}'

# With AI explanations
curl http://127.0.0.1:8000/recommend/1/explain?top_n=5
```

### Mood-Based
```bash
# List moods
curl http://127.0.0.1:8000/moods

# Get mood recommendations
curl -X POST http://127.0.0.1:8000/recommend/mood \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "mood": "intense", "top_n": 5}'
```

### Auth & Profile
```bash
# Signup
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"test123"}'

# Login (get token)
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test123"}'

# Save genres (replace YOUR_TOKEN)
curl -X POST http://127.0.0.1:8000/me/genres \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"genres":["Action","Sci-Fi","Thriller"]}'

# Get my recommendations
curl http://127.0.0.1:8000/me/recommend?top_n=10 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Chatbot
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is Inception about?","history":[]}'
```

---

## Interactive API Docs

FastAPI generates interactive docs automatically:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

You can test every endpoint directly from the browser.

---

## Troubleshooting

**"API offline" in dashboard?**
- Check the terminal — is uvicorn running?
- Run: `python scripts/preflight.py` to verify everything

**"GenAI explanation failed"?**
- Check your `GROQ_API_KEY` in `.env`
- Verify the model is set to `openai/gpt-oss-20b`
- The recommender still works — you just get fallback explanations

**"No recommendations found"?**
- Some dataset users have very few ratings
- Try a different user ID (1, 42, 100, 200 all work well)

**"User not found" when using My Account?**
- You're on the Discover tab trying a personal account username
- Personal accounts work on the "My Account" tab only
- Dataset users (1–668) work on Discover and Mood Pick tabs

---

## Files to Know

| File | What It Does |
|------|-------------|
| `.env` | Your API keys and config |
| `data/users.db` | SQLite database with your accounts |
| `data/processed/*.parquet` | Pre-built model artifacts |
| `src/app.py` | All API routes |
| `frontend/index.html` | The entire dashboard UI |

---

## What's Next?

- Read `PROJECT.md` for the full technical breakdown
- Read `PHASE2_COMPLETE.md` for what was just built
- Check `README.md` for migration notes and architecture
