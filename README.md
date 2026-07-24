# Bizfluence

A simple workspace for creators: discover fit brands, pitch partnerships, and evaluate collab offers.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Backend | FastAPI + SQLAlchemy |
| DB | SQLite locally / Postgres in production |
| LLM | Google Gemini (optional; works offline without it) |
| Email | Resend (optional; Gmail compose fallback) |

```
bizfluence/
  frontend/
  backend/
  README.md
```

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your own GEMINI_API_KEY if you have one
chmod +x run.sh
./run.sh
```

API: http://localhost:8000

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

App: http://localhost:3000

Sign in with email, or continue as a guest. New accounts are asked to set up a profile once; returning users land on Home.

## What you can do

1. **Profile** — niche, platforms, rates, and social links  
2. **Targets** — brand ideas for your niche, contacts, LinkedIn/email pitches  
3. **Offers** — paste an inbound offer and get a clear accept / negotiate / pass brief  

## Deploy notes

- Frontend (Vercel): set `NEXT_PUBLIC_API_URL` to your API  
- Backend (Render): set `DATABASE_URL`, `GEMINI_API_KEY`, `CORS_ORIGINS`, optional Resend keys  

## Auth

Email login stores a user id in `localStorage` (`X-User-Id`). Fine for MVP.
