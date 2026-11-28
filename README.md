# Bangalore Bites

AI-powered restaurant recommendations for Bangalore. Structured filters narrow the Zomato catalog; a language model ranks the short list and explains each pick.

**Live demo:** [https://web-production-805d6296.up.railway.app](https://web-production-805d6296.up.railway.app)

---

## Tech stack

| Layer | Choice |
| --- | --- |
| API | Python 3, FastAPI, Uvicorn |
| Catalog | Parquet via PyArrow / pandas; cleaned from Hugging Face `ManikaSaini/zomato-restaurant-recommendation` |
| Settings | Pydantic Settings (`.env` locally; Railway variables in production) |
| LLM | Groq OpenAI-compatible Chat Completions (`openai/gpt-oss-120b`) via `httpx` |
| Tests | pytest + FastAPI TestClient |
| Web (shipped on Railway) | Static HTML / CSS / JS served by FastAPI (`app/ui`) |
| Web (optional) | Next.js App Router in `web/` (favorites, compare, shareable URLs) for Vercel |
| Deploy | Railway (API + static UI), optional Vercel for `web/`, Docker Compose under `deploy/` |

---

## System prompt

Built in `app/recommender/prompt.py` by `build_messages(preferences, candidates)`.

### System message (current)

```text
Reply with a JSON object only. The object has "summary" and "recommendations". Each recommendation has "id", "rank", and "explanation". Every id comes from the candidate list. The number of recommendations is at most {limit}. Explanations use the extra wishes, rest type, dishes, booking flags, and review snippets. The summary is one short paragraph.
```

`{limit}` is the request’s `preferences.limit` (1–10, default 5).

### User message

1. Preference sentences (location / All Bangalore, budget, cuisine, minimum rating, extra wishes).
2. One compact block per **already-filtered** candidate:

   - `id`, `name`, `neighborhood`
   - cuisines, rest types, liked dishes
   - cost for two, rating, votes (omit null cost/rating — never invent numbers)
   - online order, table booking
   - up to two review snippets

Phone numbers and menus are never included. The model call also sets `response_format: { "type": "json_object" }` and `temperature: 0.2`.

---

## Response schema

### Model output (what the LLM must return)

```json
{
  "summary": "One short paragraph about the ranked set.",
  "recommendations": [
    {
      "id": "catalog-id-string",
      "rank": 1,
      "explanation": "Why this place fits the wishes and facts."
    }
  ]
}
```

Parsed by `parse_ranking` in `app/recommender/llm.py`. Missing `summary` / `recommendations`, non-objects, or invalid JSON raise `LlmError` and trigger the catalog fallback.

### HTTP API response (`POST /api/recommendations`)

Display fields are **always** joined from the catalog. The model only supplies rank, explanation, and summary.

```json
{
  "summary": "…",
  "applied_filters": {
    "location": "Banashankari",
    "budget": "medium",
    "cuisine": "Italian",
    "min_rating": 4.0,
    "preferences": "family-friendly"
  },
  "candidate_count": 6,
  "explanations_available": true,
  "recommendations": [
    {
      "rank": 1,
      "id": "8f3a1c…",
      "name": "Onesta",
      "location": "Banashankari",
      "cuisines": ["Pizza", "Cafe", "Italian"],
      "rest_types": ["Casual Dining", "Cafe"],
      "rating": 4.6,
      "votes": 2604,
      "cost_for_two": 600,
      "explanation": "…"
    }
  ]
}
```

Request body (`RecommendationRequest`): `location` (required); optional `budget` (`low` | `medium` | `high`), `cuisine`, `min_rating` (0–5), `preferences` (max 500 chars), `limit` (1–10, default 5).

Other endpoints: `GET /api/health`, `GET /api/locations`, `GET /api/cuisines`.

---

## Prompt versions — what changed and why

| Version | What it looked like | Why it changed |
| --- | --- | --- |
| **v0 — Architecture draft** | Four separate instructions: rank only supplied ids; use wishes / rest type / dishes / booking / reviews in explanations; return at most `limit`; respond with a documented JSON example. | Design contract in `docs/architecture.md` before Phase 4 code. |
| **v1 — Implemented system string (current)** | Same rules collapsed into one short system message; JSON field names stated inline; `limit` interpolated into the text; user message is preference prose + compact candidate blocks. | Keeps the completion focused, stays inside one Groq call, and matches what `tests/test_prompt.py` asserts (`summary`, `recommendations`, `at most {limit}`, no phone/menu leakage). |
| **Parser hardening** | Accept raw JSON or a \`\`\`json fence; drop non-string ids; ignore malformed recommendation entries. | Models sometimes wrap JSON in fences or invent numeric ids; invalid output must fall back cleanly instead of crashing the request. |

Hard filters (location, cuisine, rating, budget) stayed **out** of the prompt on purpose: the catalog already applied them. Extra wishes stay **in** the prompt only — they never remove rows.

---

## How the scope limit is enforced

Scope is enforced in layers so the model cannot invent restaurants or dump the whole city into one prompt.

### 1. Catalog filter + hard cap (`MAX_CANDIDATES`, default 15)

`CatalogStore.filter` applies location → cuisine → min rating → budget, sorts by rating/votes, then keeps only the first `max_candidates` rows. Those ids are the **only** restaurants the model is allowed to see or recommend.

### 2. Prompt contract

The system message requires every `id` to come from that candidate list and caps recommendation count at `preferences.limit`.

### 3. API validation

`limit` is constrained to **1–10** on the request model. Wishes are capped at **500** characters. Unknown locations return **422**.

### 4. Post-model validation (`RecommendationService`)

- Drop any returned id that is not in the candidate set.
- Sort by model rank and renumber from 1.
- Truncate / pad to at most `limit` (padding uses catalog order with empty explanations).
- On `LlmError` or empty filters: no invented places — empty list or catalog-order fallback up to `limit`, with `explanations_available: false`.

So: **filters + 15-candidate cap** bound the model’s world; **`limit` + id checks** bound what the user sees.

---

## Quick start (local)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\ingest.py
# copy .env.example → .env and set LLM_API_KEY
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Optional Next UI: `cd web && npm install && npm run dev` with `API_ORIGIN=http://127.0.0.1:8000`.

Deploy notes: `docs/deploy-vercel-railway.md`, `docs/deployment.md`.

---

## Project layout

```text
app/           FastAPI, catalog, recommender, static UI
web/           Next.js UI (optional Vercel front door)
data/processed restaurants.parquet
deploy/        Docker Compose + Caddy
docs/          Problem statement, architecture, phases, edge cases
scripts/       ingest + verification
tests/         unit and API tests
```

## License / data

Restaurant facts come from the public Hugging Face Zomato recommendation dataset, cleaned and deduplicated at ingest. Do not commit API keys; use `.env` locally and host secrets on Railway/Vercel.
