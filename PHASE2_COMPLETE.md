# Phase 2 — Complete ✅

**All three new features built, tested, and working.**

---

## What Was Built

### 1. Mood-Based Filtering 🎭

**Files created:**
- `src/mood.py` — mood → genre mapping + boost logic

**API:**
- `GET /moods` — list 8 mood options
- `POST /recommend/mood` — filtered recommendations with mood_match flag

**Dashboard:**
- New "Mood Pick" tab with emoji mood chips
- Click a mood → get recommendations weighted toward that vibe

**How it works:**
Each mood (e.g. "intense", "feel_good") maps to a genre cluster. When you pick a mood, movies matching those genres get a +0.25 boost to their hybrid score and re-rank to the top. Cards show a "✦ mood match" tag.

---

### 2. Movie Chatbot 💬

**Files created:**
- `src/chatbot.py` — RAG-lite keyword search + Groq call

**API:**
- `POST /chat` — send message + history, get AI reply

**Dashboard:**
- New "Ask CineMatch" tab with chat UI
- Persistent conversation history (client-side)
- Questions like "What's Inception about?" or "Recommend something like Interstellar" work

**How it works:**
Searches the movie catalogue for relevant titles using keyword + genre matching, stuffs up to 20 movies into the prompt context, sends to Groq. No vector DB needed — the 10k movie catalogue is small enough for keyword search.

---

### 3. User Accounts + Genre Onboarding 👤

**Files created:**
- `src/auth.py` — SQLite + JWT auth (fully functional, no placeholders)
- `src/user_profile.py` — cold-start recommender from genre prefs

**Database:**
- `data/users.db` created automatically (SQLite)
- Tables: `users`, `user_genres`

**API:**
- `POST /auth/signup` — create account
- `POST /auth/login` — get JWT token
- `POST /me/genres` — save genre preferences
- `GET /me/genres` — retrieve saved genres
- `GET /me/recommend` — personalized recs (content-based from prefs)
- `GET /genres` — list all 19 available genres

**Dashboard:**
- New "My Account" tab
- Login / signup forms
- Genre selection grid (multi-select chips)
- "My recommendations" section powered by saved genres
- Session persists across page reloads (localStorage)

**How it works:**
New users pick genres during onboarding. The cold-start recommender finds seed movies matching those genres, then runs the content model to score all candidates by similarity to the seeds. No rating history needed.

---

## Verification Results

✅ All 8 moods render correctly  
✅ Mood filtering boosts correct genres  
✅ Signup creates user + returns JWT  
✅ Login verifies credentials  
✅ Genre save/load works  
✅ Personalized recs based on genres  
✅ Chatbot answers movie questions  
✅ Dashboard tabs all functional  
✅ Session persistence works  

---

## How to Use It

**Start the server:**
```bash
cd movie-recommender
uvicorn src.app:app --reload
```

**Open:** http://127.0.0.1:8000

**Try this flow:**
1. Go to "My Account" → Create an account
2. Pick 3-4 genres you like → Save preferences
3. Click "Get my picks" → see personalized recommendations
4. Go to "Mood Pick" → select "🤯 Mind-Bending" → get a different vibe
5. Go to "Ask CineMatch" → type "What's Inception about?" → get an answer
6. Go to "Discover" → try the original dataset user recommendations

---

## What Changed from Phase 1

| Before | After |
|--------|-------|
| Fixed 668 dataset users only | Real user accounts with signup/login |
| No cold-start solution | Genre onboarding solves it |
| One recommendation mode | Three modes: discover, mood, personalized |
| No conversational help | Full chatbot with context |
| 10 API routes | 18 routes (+8 new) |
| Frontend: 1 panel | Frontend: 4 panels with tab navigation |
| No auth layer | JWT auth + SQLite users DB |

---

## Tech Decisions

**Why SQLite for auth?**
Zero setup, single file, good enough for local dev. Swap to RDS/DynamoDB on AWS without touching any other code.

**Why no vector DB for chat?**
The movie catalogue is 10k rows. Keyword search over titles + genres is instant and good enough. Adding ChromaDB/Pinecone would be overengineering at this scale.

**Why JWT instead of sessions?**
Stateless, Lambda-friendly, no Redis needed. The secret key lives in `.env` locally and will move to Secrets Manager on AWS.

**Why client-side chat history?**
Avoids needing a message store. For a demo/local app, keeping the last 6 turns in the browser is simpler. On AWS, you'd persist it in DynamoDB if multi-device sync matters.

---

## Files Modified

- `src/app.py` — rewrote with 8 new routes, auth middleware
- `src/config.py` — added SECRET_KEY
- `frontend/index.html` — rebuilt with 4 tabs, auth UI, mood UI, chat UI
- `.env` — added SECRET_KEY

## Files Created

- `src/mood.py`
- `src/chatbot.py`
- `src/auth.py`
- `src/user_profile.py`
- `scripts/test_new_features.py`
- `PHASE2_COMPLETE.md` (this file)

---

## Known Limitations (By Design)

**Not built (out of scope):**
- Behavioral learning (click/rating feedback loop) — deferred to Phase 3
- Password reset / email verification — not needed for local demo
- Multi-device sync — JWT works, but chat history is client-only
- Movie posters / images — focus is on the recommender, not the UI polish
- Pagination — results capped at 20, no need for infinite scroll

**Trade-offs made:**
- Chatbot uses keyword search, not embeddings — fast enough at this scale
- Auth uses PBKDF2, not bcrypt — good enough for local, easier to deploy
- No rate limiting — will add on AWS with API Gateway throttling
- Frontend is one HTML file — no build step, easier to demo

---

## Next Steps (If Continuing)

**Phase 3 ideas:**
1. Add behavioral learning — store clicks, update user profile incrementally
2. Migrate to AWS (Lambda + S3 + DynamoDB + API Gateway)
3. Add movie posters via TMDB API
4. Real email verification with SendGrid
5. Replace keyword chat search with proper embeddings (OpenAI ada-002 or sentence-transformers)

**But for now:**
This is a complete, working product with real user value. You can sign up, get personalized recommendations, explore by mood, and ask questions — all locally, all functional.
