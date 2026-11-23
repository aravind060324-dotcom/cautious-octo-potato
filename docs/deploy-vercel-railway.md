# Free deploy: Vercel (frontend) + Railway (backend)

```text
Browser ──► Vercel (Next.js in web/)
                │  rewrite /api/* 
                ▼
           Railway (FastAPI + Parquet + Groq)
```

## What you need

- GitHub repo with this project (including `data/processed/restaurants.parquet`)
- [Railway](https://railway.app) account (free trial / credits)
- [Vercel](https://vercel.com) account (Hobby)
- Groq (or compatible) API key for live explanations

## 0. Commit the catalog

Processed Parquet is required on Railway (raw CSV is not). Confirm the file exists locally:

```powershell
python scripts\ingest.py
```

Then commit `data/processed/restaurants.parquet` (~4.5 MB) with the rest of the app.

## 1. Deploy the API on Railway

1. Push the repo to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**.
3. Select this repository. Root directory = repo root (not `web/`).
4. Railway should detect Python via `nixpacks.toml` / `railway.toml`.
5. Set **variables**:

| Variable | Example |
| --- | --- |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | your Groq key |
| `LLM_MODEL` | `openai/gpt-oss-120b` |
| `CORS_ORIGINS` | `http://localhost:3000,https://*.vercel.app,https://your-app.vercel.app` |

6. Generate a public domain: **Settings → Networking → Generate domain**.  
   Copy it, e.g. `https://bangalore-bites-api.up.railway.app`.
7. Open `https://<railway-domain>/api/health` — expect:

```json
{ "status": "ok", "restaurants": 12459 }
```

If health fails, check deploy logs for a missing catalog path.

### Railway start command

Already set in `railway.toml`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 2. Deploy the frontend on Vercel

1. In Vercel: **Add New → Project → Import** the same GitHub repo.
2. Configure:

| Setting | Value |
| --- | --- |
| **Root Directory** | `web` |
| **Framework Preset** | Next.js |
| **Build Command** | `npm run build` (default) |
| **Output** | Next default |

3. Environment variables (Production + Preview):

| Name | Value |
| --- | --- |
| `API_ORIGIN` | `https://<your-railway-domain>` (no trailing slash) |

`API_ORIGIN` must be available at **build time** so `next.config.ts` rewrites `/api/*` to Railway.

4. Deploy. Open the Vercel URL (e.g. `https://bangalore-bites.vercel.app`).
5. Optional: add the exact Vercel URL to Railway `CORS_ORIGINS` (wildcard `https://*.vercel.app` already covers `*.vercel.app` previews).

## 3. Smoke test

1. `GET https://<railway>/api/health` → non-zero `restaurants`
2. Vercel home page loads Bangalore Bites
3. Search: Banashankari + Italian + medium + min rating 4
4. Confirm cards show cuisine, experience, and rating counts
5. Favorite a card → `/favorites`
6. Add two to compare → `/compare`
7. Copy the address-bar search URL into a private window — search should restore

## Local vs production

| | Local | Production |
| --- | --- | --- |
| API | `uvicorn` on `:8000` | Railway public HTTPS |
| Web | `npm run dev` in `web/` | Vercel |
| `API_ORIGIN` | `http://127.0.0.1:8000` | Railway HTTPS URL |
| CORS | localhost:3000 | Vercel hosts via `CORS_ORIGINS` |

## Common issues

| Symptom | Fix |
| --- | --- |
| Railway crash on boot | Parquet missing from git deploy — commit `data/processed/restaurants.parquet` |
| Vercel UI loads but API calls fail | Set `API_ORIGIN` on Vercel and **redeploy** (rewrites are build-time) |
| Browser CORS errors | Add the Vercel origin to Railway `CORS_ORIGINS` and redeploy API |
| No AI explanations | Set `LLM_API_KEY` on Railway; fallback list still works without it |
| Wrong app builds on Railway | Ensure service root is repo root; `nixpacks.toml` forces Python |

## Cost notes

- **Vercel Hobby**: free for personal projects  
- **Railway**: free credits / trial — watch usage; sleep or spend limits may apply  
- **Groq**: free tier for LLM calls (separate from hosting)

When Railway credits run out, the API sleeps or stops until you add credit or move the API elsewhere; the Vercel frontend can stay up but searches will fail until the API is back.
