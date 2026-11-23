# Bangalore Bites (Next.js UI)

Primary frontend for the restaurant recommendation API. FastAPI remains the catalog + LLM engine.

## Prerequisites

- Node.js 20+
- FastAPI running on `http://127.0.0.1:8000`

## Setup

```powershell
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

In another terminal, from the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

`next.config.ts` rewrites browser calls from `/api/*` to `API_ORIGIN/api/*`.

## Features

- Dark Bangalore Bites search UI
- Shareable search URLs
- Favorites (`localStorage`) at `/favorites`
- Recent searches on the home panel
- Restaurant detail drawer
- Compare tray (up to 3) at `/compare`
