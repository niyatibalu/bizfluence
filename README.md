# Bizfluence

**Everything a manager does, minus the manager.**

Bizfluence is an influencer-manager OS for creators — built India-first. It helps you find brands that fit, find the right person to pitch, send the pitch, and decide on inbound offers — without hiring a manager or living in messy spreadsheets and DMs.

Live app (frontend): [https://bizfluence.vercel.app](https://bizfluence.vercel.app)

---

## The problem

Creators who monetize with brands usually juggle three jobs at once:

1. **Figuring out who to pitch** — endless scrolling, gut feel, friend-of-a-friend intros  
2. **Actually reaching out** — LinkedIn hunts, cold emails, copy-paste pitch templates that sound like everyone else  
3. **Saying yes or no to inbound deals** — rate cards in Notes apps, vague briefs, “is this worth it?”

Managers solve that — for a cut. Most mid-size creators can’t (or don’t want to) pay one yet. Tools that exist are either sales CRMs built for agencies, or random Chrome extensions that spit out wrong contacts.

Bizfluence is the thin loop in the middle: **find fit → pitch → decide.**

---

## Who it’s for

- **Creators** (Instagram / YouTube / LinkedIn) who already post and want brand deals without a full-time manager  
- Especially **India D2C / lifestyle / tech / beauty** creators pitching local and global brands  
- Solo creators and tiny teams who want one place for targets, pitches, and offer decisions  

Not for: large agencies running hundreds of talent seats (yet).

---

## What you can do today

| Step | What happens |
|---|---|
| **Profile** | Niche, audience, rates, hard no-gos, and your real social links |
| **Research** | Bizfluence reads *your* Instagram / YouTube / LinkedIn / other links (not random people with similar names) |
| **Targets** | Brand ideas matched to your niche + research |
| **Contacts** | People to pitch for a brand, with LinkedIn links you can open and check |
| **Pitch** | LinkedIn DM + cold email drafted for that brand and contact |
| **Offers** | Paste an inbound offer → get a plain-language accept / negotiate / pass brief |

That’s the whole product loop. Everything else waits until this feels good.

---

## How to use it

1. Open the app and **sign in** (email) or **continue as guest**.  
2. New accounts land on **Profile** — fill niche, audience, rates, and paste your real IG / YouTube / LinkedIn. Save.  
3. Go to **Targets** → get brand ideas. Open a brand.  
4. Hit **Find contacts**. Open LinkedIn links to verify before you message anyone. Add someone manually if search misses.  
5. **Generate pitch** → copy the LinkedIn DM or email and send it yourself.  
6. When a brand replies with a deal, go to **Offers**, paste the brief, and use the accept / negotiate / pass notes.

Tip: bio and research notes are **context for the app**, not text to paste into pitches.

---

## What’s next (product)

Near-term:

- Stronger contact accuracy for India brands  
- Better offer negotiation helpers  
- Public deploy + real accounts for early creators  

Later (only after the web loop feels right):

- Browser extension for “pitch this brand from the page you’re on”  
- Events / creator meetups as a discovery surface  
- Deeper inbox / CRM without becoming Salesforce  

Gemini (optional) polishes writing when a key is set; without it, the app still runs on offline writers.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Backend | FastAPI + SQLAlchemy |
| DB | SQLite locally / Postgres on Render |
| LLM | Google Gemini (optional) |
| Email send | Resend (optional; Gmail compose fallback) |

```
bizfluence/
  frontend/     # Next.js app (Vercel)
  backend/      # FastAPI API (Render)
  render.yaml   # Render blueprint
  README.md
```

Repo: [github.com/niyatibalu/bizfluence](https://github.com/niyatibalu/bizfluence)

---

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: GEMINI_API_KEY, HUNTER_API_KEY, RESEND_*
chmod +x run.sh
./run.sh
```

API: http://localhost:8000 · health: http://localhost:8000/health

### Frontend

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000/api
npm install
npm run dev
```

App: http://localhost:3000

---

## Deploy

### Status

- **Frontend:** live on Vercel → [bizfluence.vercel.app](https://bizfluence.vercel.app)  
- **Backend:** deploy via Render Blueprint (below), then point the frontend at it  

### Backend (Render) — do this next

1. Open [Render Blueprints](https://dashboard.render.com/blueprints) → **New Blueprint Instance**.  
2. Connect GitHub and select **`niyatibalu/bizfluence`** (branch `main`).  
3. Apply `render.yaml` — creates **bizfluence-api** + free Postgres.  
4. On the **bizfluence-api** service → **Environment**, set:  
   - `CORS_ORIGINS` = `https://bizfluence.vercel.app`  
   - optional: `GEMINI_API_KEY`, `HUNTER_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`  
5. Deploy. Copy the service URL (e.g. `https://bizfluence-api.onrender.com`).  
6. Free Postgres expires after **30 days** unless you upgrade.

**If the Blueprint sync or build fails:** Render only allows one free Postgres per account — delete any unused free DB, then sync again. Also confirm the service uses Python **3.11** (`runtime.txt` + `PYTHON_VERSION`). Check **bizfluence-api → Logs → Build** for the real pip error.

### Wire the frontend to the API

1. [Vercel project](https://vercel.com/niyati2/bizfluence) → **Settings** → **Environment Variables**.  
2. Add `NEXT_PUBLIC_API_URL` = `https://YOUR-RENDER-HOST/api` (Production + Preview).  
3. **Redeploy** the frontend (Deployments → … → Redeploy), or from the repo:

```bash
cd frontend
npx vercel --prod
```

Until that env var is set, the live site still talks to localhost and won’t load data in production.

### Auth note

Email login stores a user id in `localStorage` (`X-User-Id`). Fine for MVP; not full OAuth yet.
