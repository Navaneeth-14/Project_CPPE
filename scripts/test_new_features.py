"""Quick end-to-end test of the three new features."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import app
from fastapi.testclient import TestClient
import time

client = TestClient(app)

print("Testing new features...")
print()

# 1. Moods endpoint
r = client.get('/moods')
assert r.status_code == 200
moods = r.json()
assert len(moods) == 8
print(f'✓ GET /moods → {len(moods)} moods available')

# 2. Mood recommend
r = client.post('/recommend/mood', json={'user_id':1,'mood':'intense','top_n':5})
assert r.status_code == 200
data = r.json()
assert len(data['recommendations']) == 5
assert data['mood'] == 'intense'
print(f'✓ POST /recommend/mood → {len(data["recommendations"])} results for "intense" mood')

# 3. Signup
uname = f'test{int(time.time())}'
r = client.post('/auth/signup', json={'username':uname,'email':f'{uname}@test.com','password':'test123'})
assert r.status_code == 200
auth = r.json()
assert 'token' in auth
token = auth['token']
print(f'✓ POST /auth/signup → new user "{uname}" created')

# 4. Login
r = client.post('/auth/login', json={'username':uname,'password':'test123'})
assert r.status_code == 200
print(f'✓ POST /auth/login → login successful')

# 5. Save genres
r = client.post('/me/genres', json={'genres':['Action','Sci-Fi','Thriller']}, headers={'Authorization':f'Bearer {token}'})
assert r.status_code == 200
print(f'✓ POST /me/genres → saved 3 genres')

# 6. Get saved genres
r = client.get('/me/genres', headers={'Authorization':f'Bearer {token}'})
assert r.status_code == 200
saved = r.json()
assert set(saved['genres']) == {'Action','Sci-Fi','Thriller'}
print(f'✓ GET /me/genres → retrieved saved genres')

# 7. Get personalized recs
r = client.get('/me/recommend?top_n=5', headers={'Authorization':f'Bearer {token}'})
assert r.status_code == 200
data = r.json()
assert len(data['recommendations']) == 5
assert data['username'] == uname
print(f'✓ GET /me/recommend → {len(data["recommendations"])} personalized recommendations')

# 8. Chat
r = client.post('/chat', json={'message':'What is Inception about?','history':[]})
assert r.status_code == 200
chat = r.json()
assert 'reply' in chat
assert len(chat['reply']) > 20
print(f'✓ POST /chat → chatbot replied ({len(chat["reply"])} chars)')

# 9. All genres list
r = client.get('/genres')
assert r.status_code == 200
genres = r.json()
assert len(genres['genres']) == 19
print(f'✓ GET /genres → {len(genres["genres"])} genres for onboarding')

print()
print("=" * 55)
print("  🎉 All 9 new feature endpoints working perfectly")
print("=" * 55)
