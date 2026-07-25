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

## Deploy

### Backend (Render)

1. Push this repo to GitHub.
2. In [Render](https://dashboard.render.com) → **New** → **Blueprint** → select `niyatibalu/bizfluence`.
3. Apply `render.yaml` (creates `bizfluence-api` + free Postgres).
4. Set env vars on the service:
   - `CORS_ORIGINS` = your Vercel URL (e.g. `https://bizfluence.vercel.app`)
   - optional: `GEMINI_API_KEY`, `HUNTER_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`
5. After deploy, API is at `https://bizfluence-api.onrender.com` (exact URL is in the Render dashboard).

Free Postgres expires after 30 days unless upgraded.

### Frontend (Vercel)

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to `https://YOUR-RENDER-HOST/api` (Project → Settings → Environment Variables), then redeploy.

Or connect the GitHub repo in the Vercel dashboard with **Root Directory** = `frontend`.

## Auth

Email login stores a user id in `localStorage` (`X-User-Id`). Fine for MVP.
