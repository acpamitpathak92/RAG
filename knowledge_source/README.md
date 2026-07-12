# AI Travel Planner & Visa Assistant — Architectural Spine

A provider-agnostic, multi-agent travel-planning backend built on **LangGraph +
MCP-style tool boundaries + FastAPI**. It produces a complete `TravelPlan`
(destination research, day-wise itinerary, costed budget, weather, packing,
transport, hotels, food, visa) with an evaluation/confidence pass.

**Design principles** (deterministic where it matters, LLM only for prose):

- **Deterministic in code, LLM for narrative only.** All numbers — budget, FX,
  cost lines, confidence score, validation — are computed in plain Python and
  are reproducible. LLMs write only the `narrative` fields.
- **MCP tool boundary.** Every external capability is a named tool
  (`visa.check`, `currency.convert`, `weather.forecast`, …). Agents depend on
  tool names, not transports — swap an in-process adapter for a remote MCP
  server via config, no agent changes.
- **Env-driven provider selection.** Anthropic / OpenAI / Gemini / Groq /
  OpenRouter / Azure OpenAI / Ollama, auto-selected by which key is present.
- **Graceful offline fallback.** Runs end-to-end with **zero API keys** using
  deterministic offline data; the evaluation agent flags offline/low-confidence
  sections.
- **Parallel fan-out.** Independent agents run concurrently (LangGraph
  supersteps, or a bounded async runner when LangGraph isn't installed).

## Project layout

```
travel-planner/
  backend/     FastAPI + LangGraph + MCP adapters (Python)   ← .env lives here
  frontend/    Vite + React UI
```

## Quick start

**Backend**

```bash
cd backend
pip install -r requirements.txt
# .env is already included (live weather/FX/food/transport need no keys);
# add provider/API keys to it when you want them.

python -m app.main                       # offline CLI demo, prints a full plan
uvicorn app.main:app --reload            # API on :8000  (POST /plan, /plan/stream)
pytest -q                                # 23 tests, no keys needed
python smoke_test.py                     # prints live-vs-offline per adapter
```

**Frontend** (Vite + React, in `frontend/`)

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

The form collects the trip details, calls `POST /plan` (Vite proxies it to the
backend on :8000), and renders the plan: a boarding-pass summary, day-wise
itinerary, cost dashboard, weather strip, visa + live advisory, food, transport,
hotels, packing, and a plan-check panel. Live sections show a **live/offline
badge**. Run the backend first; CORS is enabled for the dev server origin.

## Workflow

```
research ─► [ cost | weather | hotels | food | visa | transport ]   (parallel)
                              │
                     ► packing   (needs weather)
                     ► itinerary (needs research)
                              │
                          ► evaluation ─► TravelPlan
```

LangGraph is the canonical orchestrator (`build_graph()`); an equivalent async
fan-out runner is used automatically if LangGraph isn't installed. Both call the
identical agent node functions.


## Seeing what's live vs offline (terminal logs)

The backend logs every fallback to the terminal, so you can see exactly why a
section isn't live. After each plan you'll get a summary line, e.g.:

```
travel.plan | PLAN Pune->Sydney | llm=groq weather=live:open-meteo food=live:llm transport=live:llm journey=live:travelpayouts visa_adv=live
```

If something fails you'll see the cause just above it, e.g.:

```
travel.llm  | LLM gemini FAILED -> RuntimeError: HTTP 400: API key not valid
travel.llm  | LLM: using groq (model=llama-3.3-70b-versatile)
travel.http | GET overpass-api.de failed after 1 tries: ReadTimeout
travel.food | Google Places (food) status=REQUEST_DENIED: ... — enable the Places API
```

Common fixes: a `gemini` HTTP 400/403 means a bad key or model name (the app
auto-falls back to your other keys); `REQUEST_DENIED` from Google means the
**Places API** isn't enabled on that key; Overpass timeouts are normal (the LLM
covers food/transport). Set `LOG_LEVEL=DEBUG` for more detail.

## Reliability & fallbacks

- **LLM circuit-breaker:** a provider that returns 429/quota/auth errors is put
  in cooldown (300s) and skipped, so the app sticks to a working provider (e.g.
  Groq) instead of re-hitting a rate-limited one on every call.
- **Google Places API (New):** food/hotels use `places.googleapis.com` (the
  legacy Text Search is disabled on new keys). Enable **"Places API (New)"** on
  your key for `live:google` venues; otherwise the LLM provides them.
- **Keyless-first weather/FX:** Open-Meteo and open.er-api.com are tried before
  any keyed provider, so an invalid WEATHER_API_KEY / FX_API_KEY no longer breaks
  or spams — those keyed providers are only a secondary.

- **Multi-provider LLM fallback:** if your chosen provider errors (bad key, model
  access, etc.) the client automatically tries any other configured provider
  (e.g. Gemini -> Groq), so content still generates. `provider_used` reports the
  one that actually worked, and `GET /health/llm` shows the real error if all fail.
- **Seasonal weather:** trips beyond the ~16-day forecast window use Open-Meteo's
  archive for the same dates last year (so a December trip shows December weather),
  labelled `live:open-meteo-seasonal`.
- **Flights:** the "Getting there" card shows Economy / Direct / Business options
  with per-person estimates and **Google Flights booking links**. Domestic trips
  show train / bus / cab / flight with booking/search links.

## Troubleshooting: getting placeholder / "offline mode" output?

If `provider_used` is `offline` and narratives say "offline mode", the LLM isn't
being used. Checks, in order:

1. **Keys go in `backend/.env`** (same folder as `requirements.txt`). The file is
   auto-loaded — even without `python-dotenv` installed there's a built-in loader.
2. **Confirm it's live:** start the backend and open `GET /health/llm`, or run
   `python smoke_test.py`. You want `provider: gemini` (or your provider) and
   `ok: true`. If it returns an error, the message is the real reason (bad key,
   wrong model name, blocked network).
3. **Use a real city.** `destination_city` must be a city (e.g. *Sydney*), not a
   country (*Australia*) — a country geocodes to its centroid and weakens food/
   transport lookups.
4. Re-run `pip install -r requirements.txt` if you installed before adding keys.

Gemini is called via REST, so **no SDK install is needed** for `LLM_PROVIDER=gemini`.

## Content generation (needs an LLM key)

Real-world *content* — which attractions to see, the day-by-day plan, local
dishes, and hotel suggestions — comes from the **LLM** as structured JSON, while
deterministic code handles costing, FX, day-count enforcement, dedup, validation
and confidence. Set any one provider key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`, …) in `backend/.env` and these become genuine, city-specific.
With **no** LLM key the planner still runs but uses generic placeholder
attractions/hotels — so for real itineraries, set a key.

> New: add a **From (city)** for domestic trips — when source and destination
> countries match (e.g. within India), the plan shows real **train / bus / cab /
> flight** options with costs and times. International trips show flight details.

> Tip: `destination_city` must be an actual city (e.g. *Sydney*), not a country
> (*Australia*). A country name geocodes to the centroid and degrades food /
> transport lookups; the city drives geocoding and the LLM prompts.

## Backend layout (`backend/`)

```
app/
  config.py            env settings (no hardcoded secrets)
  models/schema.py     Pydantic contracts (single source of truth)
  llm/provider.py      provider-agnostic client + auto-select + offline narrator
  mcp/                 MCP-style tool adapters (registry, TTL cache, live+offline)
    base.py  http.py  currency.py  weather.py  maps.py  flights.py  visa.py  catalog.py
  cost/engine.py       deterministic budget math
  agents/              10 agents (research, parallel branches, planning, evaluation)
  graph/               LangGraph state + workflow (+ async fallback)
  main.py              FastAPI app + streaming + CLI demo
tests/test_core.py     unit + full-pipeline tests
```

## Live data adapters

Every external capability degrades cleanly: **keyed provider → keyless live → offline**.

| Tool | Live, no key | Live, keyed | Offline fallback |
|------|--------------|-------------|------------------|
| `weather.forecast` | Open-Meteo (geocode + forecast + us_aqi) | `WEATHER_API_KEY` (weatherapi.com) | seasonal heuristic |
| `currency.convert` | open.er-api.com | `FX_API_KEY` (exchangerate-api v6) | static USD table |
| `food.search` | OpenStreetMap Overpass (real venues, diet tags) | `GOOGLE_MAPS_API_KEY` (Places) | small static list |
| `transport.options` | OSM Overpass (detects metro/tram/bus/bike that *exist*) | — | generic mode list |
| `maps.geocode` / `maps.distance` | OSM geocoder + OSRM router | `GOOGLE_MAPS_API_KEY` | haversine + road factor |
| `advisory.get` | travel-advisory.info (risk score + message) | — | none |
| `flight.search` | — (no keyless pricing exists) | `TRAVELPAYOUTS_TOKEN` | seeded estimate |
| `visa.check` | — (no reliable free real-time source) | (plug your source) | illustrative ruleset |

So **weather, currency, food, transport, maps and travel advisories return real data
with zero config**. Each response carries a `source` (`live:*` or `offline`); the
four traveller-facing sections (weather, food, transport, visa-advisory) surface
that as a **live/offline badge in the UI**, and the evaluation agent flags offline
sections.

**On "real-time":** weather/FX are genuinely current; food/transport/maps use
live community POI + routing data (current, not minute-by-minute departures);
advisories are daily-updated government risk data. Visa *requirements* stay a
flagged ruleset — no free API publishes them reliably, so the planner marks
unverified routes low-confidence rather than inventing rules. Hotel and flight
pricing have no free real-time source either (flights need a Travelpayouts token).

**Verification note:** live parsers are unit-tested against payloads shaped like
each real API (`tests/test_live_parsers.py`) and graceful fallback is verified,
but outbound calls were not exercised from the build sandbox (network-restricted).
Run on a connected machine to see live data populate.

## What's implemented vs. extension points

**Done and runnable:** provider abstraction with offline fallback; MCP adapter
pattern + TTL cache + shared HTTP helper (timeout/retry/network-gate);
**live** weather/FX/maps adapters (keyless) and keyed Google/weatherapi/Travelpayouts
paths; deterministic cost engine; all 10 agents; LangGraph graph with parallel
fan-out + async fallback; evaluation/confidence; FastAPI with SSE streaming;
13 tests (deterministic core + live-parser); `.env.example`.

**Not in this spine** (deliberately deferred — say the word and I'll add any of
them): React + Vite frontend, i18n bundles, Docker/compose, persistence schema,
and a real visa data source behind `visa.check`.

> Visa data is a small illustrative ruleset. Visa rules change constantly — the
> evaluation agent marks unverified routes low-confidence by design. Do not ship
> visa output without a real source behind `visa.check`.
