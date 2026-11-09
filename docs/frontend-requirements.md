# Frontend requirements: station overview and station monitoring

Status: **ready to start** · Owner: **Ice (Nattapat Rueangput)** · Target: working on Azure before Phase 3 (16 Nov 2026)

This is the brief for building the dashboard in `apps/web`. It says what to build, in what order, and how we will know
each part is done. Visual rules are in [apps/web/DESIGN.md](../apps/web/DESIGN.md). How the web app works and how to
run it is in [apps/web/README.md](../apps/web/README.md).

## 1. Background (read first, 5 minutes)

- We forecast **tomorrow's solar power** for four PEA plants (S01 to S04), every 15 minutes, which gives 96 values per
  plant per day. Each value has a P50 (median) and a P10–P90 range, in kW.
- The model runs once a day as a batch job in the ML repo
  ([Solar_Power_Prediction](https://github.com/pcismyname/Solar_Power_Prediction)). It writes JSON files, and the
  FastAPI service in `apps/api` serves them. **The dashboard only reads from that API.**
- The ML proposal (§3.2) commits the dashboard to showing, per plant: **the next-day 15-min profile, total daily
  energy, issue time, forecast age, model version and fallback status, plus a CSV/JSON download.**
- Out of the box, the API runs in **demo mode** and returns synthetic curves. You do not need any real data or Azure
  access to build the whole frontend.

## 2. What the user sees

```
 ┌───────────────────────── /  (Station overview) ─────────────────────────┐
 │ Solar Day-Ahead Forecast                         ● API online           │
 │ Forecast for Tue 27 Oct 2026 · All times Asia/Bangkok (UTC+7)           │
 │ ┌ Total energy (4 plants) ┐ ┌ Plants with forecast ┐ ┌ Latest issue ┐   │
 │ └─────────────────────────┘ └──────────────────────┘ └──────────────┘   │
 │ ┌ S01 Sa Kaeo ──────┐ ┌ S02 Prachuap ─────┐ ┌ S03 ... ┐ ┌ S04 ... ┐     │
 │ │ ● Forecast ready  │ │ ⚠ Fallback model  │ │         │ │ ✖ Missing│    │
 │ │ ⌒ sparkline P50   │ │ ⌒                 │ │         │ │         │     │
 │ │31.2 MWh · 5,100 kW│ │ ...               │ │         │ │         │     │
 │ │ cap 6,000 kW      │ │                   │ │         │ │         │     │
 │ │ issued 2 h ago    │ │                   │ │         │ │         │     │
 │ └───────────────────┘ └───────────────────┘ └─────────┘ └─────────┘     │
 └─────────────────────────── click a card ↓ ──────────────────────────────┘
 ┌──────────────────── /station/?id=S01  (Station monitoring) ─────────────┐
 │ ← All stations   S01 Sa Kaeo · 6,000 kW            [◀] 2026-10-27 [▶]   │
 │ ┌ Forecast energy P50 ┐ ┌ Peak power P50 ┐ ┌ Peak / capacity ┐          │
 │ ┌──────────── Chart (8 cols) ─────────────┐ ┌ Status (4 cols) ───────┐  │
 │ │ P50 line + P10–P90 band, hover readout  │ │ Issued · age · model   │  │
 │ │                                         │ │ mode · alerts          │  │
 │ └─────────────────────────────────────────┘ │ [Download CSV] [JSON]  │  │
 │ ┌──────────── 96-row table (collapsible) ─────────────────────────────┐ │
 └─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Page `/`: station overview

| # | Requirement |
|---|---|
| O1 | Loads the plant list (`GET /api/v1/plants`), then **tomorrow's** forecast for every plant **in parallel** (`GET /api/v1/forecast`). "Tomorrow" means tomorrow in Asia/Bangkok, computed in the browser (`tomorrowInBangkok()` in `lib/format.ts`). |
| O2 | KPI row: **total P50 energy for all plants** (kWh, only from plants that have a complete forecast, labelled "*n* of 4 plants"), **plants with a forecast** ("3 / 4"), and **latest issue time**. |
| O3 | One **station card** per plant: name and ID, capacity, a status badge, a P50 **sparkline**, P50 energy (kWh) and peak (kW), and "issued *x* h ago" (same future-time rule as S5: if `issued_at` is in the future, show the issue time and no age). |
| O4 | Status badge rules: `● Forecast ready` (ok) · `⚠ Stale` (warn, issued more than 36 h ago) · `⚠ Fallback: cached weather` / `⚠ Fallback: climatology` / `⚠ Fallback: baseline` (warn, names the `forecast_mode`, see §4) · `✖ No forecast` (bad, API 404) · `✖ Error` (bad, any other failure). If several apply, show only the first in this order: Error > No forecast > Fallback > Stale > Ready. Detect 404 with `err.status === 404` (see FE-1), never by parsing the message. |
| O5 | The whole card links to `/station/?id=<plant_id>`. It works with the keyboard (Tab + Enter) and shows a visible focus ring. |
| O6 | If one plant's forecast fails, **the other cards still render**. A failure must not blank the page. |
| O7 | API status pill in the header (this exists today: it polls `/health` every 60 s). If the API is offline, show one alert banner with the API URL instead of four broken cards. |

### 2.2 Page `/station/?id=S01`: station monitoring

| # | Requirement |
|---|---|
| S1 | Reads `id` from the query string. If the ID is unknown or missing, show "Station not found" and a link back. Do **not** crash. |
| S2 | Header: `← All stations` back link, station name, capacity. A **date picker** plus previous/next-day buttons. The default date is tomorrow (Bangkok). The selected date is kept in the URL (`&date=YYYY-MM-DD`), so a link can be shared. |
| S3 | KPI row: **forecast energy P50** (kWh = Σ p50 × 0.25 h), **peak power P50** (kW, with its time), and **peak / capacity** (%). |
| S4 | **Main chart** (8 columns): P50 line, P10–P90 band, y-axis from 0 to capacity, an x-axis every 3 h, and a hover readout of time and P10/P50/P90. Restyle the existing `ForecastChart.tsx`; do not add a chart library. |
| S5 | **Status panel** (4 columns): issued at (Bangkok time), **forecast age** ("issued 14 h ago"), model version, forecast mode (§4), point count ("96 × 15 min"), and any alerts (missing, stale, fewer than 96 points, fallback). If `issued_at` is in the future (the demo API does this), show the issue time without an age. Never show a negative age. |
| S6 | **Download** buttons: CSV (`timestamp,p10_kw,p50_kw,p90_kw`) and JSON (the API response as-is). Build both in the browser from data already loaded; this needs no new endpoint. File name: `forecast_S01_2026-10-27.csv`. |
| S7 | **Data table**: 96 rows (time, P10, P50, P90), collapsed by default and opened with a "Show table" button. Numbers are right-aligned in the monospace font. Night rows (all zeros) may be dimmed. |
| S8 | Loading, empty (404 "no forecast for this date") and error states are all designed. Do not show a blank chart. |

### 2.3 Shared

| # | Requirement |
|---|---|
| G1 | Follows [DESIGN.md](../apps/web/DESIGN.md): dark theme, tokens in `globals.css`, Inter + JetBrains Mono through `next/font/google`. |
| G2 | Usable at **1280 px** (laptop) and **768 px** (tablet). At 375 px (phone), content stacks with no horizontal scroll. |
| G3 | Shows every time in **Asia/Bangkok** and says so once per page. Never shows browser-local time. |
| G4 | Every number has its unit. Show energy above 10,000 kWh as MWh with one decimal. |
| G5 | All API calls go through `lib/api.ts`. Types stay in sync with the API (AGENTS.md rule 4). TypeScript strict, no `any`. |

## 3. Technical constraints (do not break these)

- **Static export only** (`output: "export"`). No API routes, server actions or server-side fetching. All data
  loading happens in `"use client"` components. See `apps/web/README.md` → *Constraints of static export*.
- **Why `/station/?id=S01` and not `/stations/S01`:** a dynamic route like `[id]` in a static export needs every ID
  known at build time (`generateStaticParams`). That would make the build depend on the API or a copy of the
  plant list. A query parameter avoids both. Use `useSearchParams()` inside a `<Suspense>` boundary, or follow the
  `dynamic(..., { ssr: false })` pattern already used in `app/page.tsx`.
- **No new dependencies** without a short note in the PR saying why. Hand-written SVG is enough for the chart and
  sparkline. Do not add a UI kit or chart library.
- **No real PEA data** in code, fixtures, screenshots or commits. Use demo mode only.

## 4. Contract gap: forecast mode / fallback status

The proposal requires a **fallback status** (primary model / cached weather / climatology / baseline), but the current
forecast JSON has no field for it. Plan:

1. **Frontend now:** treat it as optional. Add `forecast_mode?: "primary" | "cached_weather" | "climatology" |
   "baseline"` to the `Forecast` type in `lib/api.ts`. Show "Mode: primary" when the field is missing, and the
   a fallback badge that names the mode (`⚠ Fallback: climatology`) when the value is anything other than `primary`.
2. **Backend (ticket BE-1):** add the optional field to `apps/api/app/schemas.py` and the demo provider. Then update
   the contract in `apps/api/README.md` **and** open the matching PR in the ML repo, because the contract is shared.
   Do not merge the field in only one repo.

## 5. Out of scope (for now)

- **Actual vs forecast (live accuracy monitoring).** There is no live PEA data feed in the cloud, and raw
  measurements are confidential, so they must not appear on a public page. Accuracy is reported from the ML repo's
  local replay. If PEA later allows a data feed, this becomes a separate decision record.
- Login, user accounts, databases, Next.js server features (see `docs/architecture.md`).
- ~~A map of plants~~ Added to the overview page as a station map. S03/S04 show under "Location not confirmed" until
  PEA confirms their coordinates; adding `lat`/`lon` in `apps/api/app/plants.py` places them automatically.
- Light mode, translations (Thai UI), cost in THB.

## 6. Tickets

Do them roughly in this order. **FE-1 is the foundation, so merge it first.** After it, FE-2 to FE-6 can run in
parallel by different people.

| ID | Ticket | Depends on | Size | Done when |
|---|---|---|---|---|
| FE-1 | **Design tokens + app shell**: replace colours in `globals.css` with the DESIGN.md tokens (dark only), load fonts through `next/font`, add a shared header (title, API status pill, time-zone note) and a 12-column layout container. In `lib/api.ts`, add an `ApiError` class with a `status` field (thrown by `getJson`), and change `Plant.lat`/`lon` to `number \| null` (the API returns `null` for S03/S04). Switch the chart's `.grid` from `--grid` to `--border` | – | S | Existing page renders in the new theme; lint, typecheck and build pass |
| FE-2 | **Overview page**: O1–O7, including the `StationCard` component and the `Sparkline` component | FE-1 | M | 4 cards from demo API; one plant failing (e.g. stop the API mid-load, or mock 404) leaves the others intact |
| FE-3 | **Station page skeleton**: route `/station/`, `id`/`date` query params, header, date navigation, KPI row (S1–S3, S8) | FE-1 | M | Deep link `/station/?id=S02&date=2026-10-20` opens the right plant and date; unknown ID shows "not found" |
| FE-4 | **Chart restyle**: `ForecastChart` to DESIGN.md (S4), plus touch support for the hover readout on tablets | FE-1 | S | Chart matches tokens; readout works with mouse and touch |
| FE-5 | **Status panel + alerts**: S5, the shared `Alert` and `StatusBadge` components (also used by FE-2), `forecast_mode` optional type (§4) | FE-1 | S | Stale, missing, fallback and short-points states each render. Missing: file provider (§8). Stale: pick a past date. Fallback and fewer than 96 points cannot come from the API (the API rejects short forecasts with 500, and `forecast_mode` needs BE-1), so test them with a mocked response in the frontend |
| FE-6 | **Downloads + data table**: S6, S7 | FE-3 | S | CSV opens correctly in Excel with 96 rows + header; JSON equals the API response |
| FE-7 | **Responsive + accessibility pass**: G2, keyboard navigation, `aria-label`s on charts, colour never the only signal | FE-2, FE-3 | S | Checked at 1280 / 768 / 375 px; Lighthouse accessibility score of 90 or more on both pages |
| FE-8 | **Docs**: update `apps/web/README.md` (pages, components, file map), and add screenshots to the PR | FE-2, FE-3 | XS | README matches the code |
| BE-1 | **API `forecast_mode` field** (§4), with tests, contract docs and the paired ML-repo PR | – | S | `pytest` green; the field appears in `/docs`; ML repo PR linked |

Sizes: XS takes under 2 h, S is about half a day, and M is 1–2 days.

## 7. Definition of done (every frontend PR)

- [ ] Branch `feat/<ticket-id>-short-name`, PR into `main`, one review, CI green (AGENTS.md).
- [ ] `cd apps/web && npm run lint && npm run typecheck && npm run build` all pass locally (same as CI). Paste the result in the PR.
- [ ] Tested against the local API in demo mode (`docker compose up --build`, or run `apps/api` with uv).
- [ ] Screenshots at 1280 px and 768 px in the PR description.
- [ ] Uses only DESIGN.md tokens (no new hex codes in components). No `any`. No new dependency without a reason.
- [ ] No real plant data anywhere.

## 8. Getting started (first hour)

```bash
git switch main && git pull
cd apps/api && uv sync && uv run uvicorn app.main:app --reload     # terminal 1 → http://localhost:8000/docs
cd apps/web && npm ci && cp .env.example .env.local && npm run dev # terminal 2 → http://localhost:3000
```

**Testing failure states.** Demo mode returns a forecast for every known plant and every date, so it never gives a
404. To see the "No forecast" state, run the API with the file provider and an empty folder:
`FORECAST_PROVIDER=file FORECAST_DIR=./empty uv run uvicorn app.main:app --reload` (Git Bash/macOS/Linux) or
`$env:FORECAST_PROVIDER="file"; $env:FORECAST_DIR="./empty"; uv run uvicorn app.main:app --reload` (PowerShell).
You can also put both variables in `apps/api/.env`. Every forecast then returns 404,
while `/api/v1/plants` still works. To see "API offline", stop the API.

Then read, in this order: [apps/web/README.md](../apps/web/README.md) → [apps/web/DESIGN.md](../apps/web/DESIGN.md) →
`lib/api.ts` → `components/Dashboard.tsx`. Today's single-page dashboard already has the data loading, the race-safe
forecast fetch and the chart. Reuse it rather than starting again.
