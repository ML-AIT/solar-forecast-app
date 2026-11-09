# apps/web — Solar Forecast Dashboard (Next.js)

A responsive, dark-mode dashboard that presents day-ahead 15-minute PV power forecasts
(P50 median curve with P10–P90 uncertainty band) for PEA solar plants. It is a **static site**:
Next.js exports pre-rendered HTML/JS/CSS into `out/`, and the client fetches data dynamically
from the FastAPI backend (`apps/api`).

All visual rules and tokens adhere to [DESIGN.md](DESIGN.md). Full functional requirements
and ticket definitions are specified in [docs/frontend-requirements.md](../../docs/frontend-requirements.md).

## Stack

- **Framework**: Next.js 16 (App Router, static export `output: "export"`), React 19, TypeScript (strict)
- **Styling**: Pure CSS with CSS modules and design tokens from `DESIGN.md` in `app/globals.css` (dark mode only)
- **Typography**: `Inter` (UI, headings, body) and `JetBrains Mono` (tabular numbers, KPIs, timestamps) loaded via `next/font/google`
- **Charts**: Custom, lightweight SVG charts and sparklines (`ForecastChart.tsx`, `Sparkline.tsx`) with zero external charting dependencies
- **Linting & Quality**: ESLint 9, strict typechecking

## Pages & User Flows

1. **Station Overview (`/`)**:
   - High-level system KPIs: Total forecast energy (P50) across complete plants (formatted in kWh or MWh), plant readiness count, and latest issue time.
   - 4-station card grid (8 columns, 2 × 2): Shows plant capacity, P50 sparkline, P50 energy, peak power, and status badges (`● Forecast ready`, `⚠ Stale`, `⚠ Fallback: cached weather` / `⚠ Fallback: climatology` (names the `forecast_mode`; the same text on the map and the station page), `✖ No forecast`, `✖ Error`).
   - **Station map** (right 4 columns, stacks under the cards below 1024 px): an SVG map of Thailand with one marker per plant that has coordinates, coloured and labelled by status. Hovering or focusing a marker highlights its card (and the reverse) and shows a tooltip; clicking opens the station page. Plants without coordinates (`lat`/`lon` = `null`) are listed under "Location not confirmed".
   - Fault-resilient parallel loading: Failure of one plant does not break other cards.
   - Header with API health polling every 60 seconds and Asia/Bangkok (`UTC+7`) timezone indication.
   - Offline alert banner shown when the API backend cannot be reached.

2. **Station Monitoring (`/station/?id=S01`)**:
   - Deep-linked by query parameters (`?id=S01&date=YYYY-MM-DD`). Gracefully handles missing or unknown IDs with a "Station not found" view.
   - Header with back link (`← All stations`), plant name, capacity, and date navigation (`[◀]`, date picker input, `[▶]`).
   - KPI row: Forecast energy P50 (kWh/MWh), peak power P50 (kW with timestamp), and peak-to-capacity ratio (%).
   - Main 12-column layout (8 columns chart + 4 columns status/alerts):
     - **Generation profile chart**: P50 line, P10–P90 uncertainty band, capacity threshold line, and mouse/touch scrub readout.
     - **Status panel**: Model version, issue timestamp, forecast age (future-proofed against negative values), resolution, active alert banners (missing, stale, fallback, incomplete), and browser-side **CSV** and **JSON** download buttons.
   - **Collapsible data table**: 96 rows of 15-minute interval power values with right-aligned tabular figures and dimmed night intervals.

## Files Map

| File | Purpose |
|---|---|
| `app/page.tsx` | Overview page entrypoint (dynamic client import) |
| `app/station/page.tsx` | Station monitoring page entrypoint (with `<Suspense>`) |
| `app/layout.tsx` | Root layout configuring Inter and JetBrains Mono fonts |
| `app/globals.css` | Design tokens (dark palette), focus ring utilities, and `.sr-only` class |
| `lib/api.ts` | Backend client, TypeScript contracts (`Plant`, `Forecast`, `ForecastPoint`), and `ApiError` |
| `lib/format.ts` | Bangkok timezone formatting, number/energy formatting, date shifting, and staleness checks |
| `lib/export.ts` | In-browser CSV (`timestamp,p10_kw,p50_kw,p90_kw`) and JSON file export helpers |
| `components/Header.tsx` | Shared top navigation with title, timezone label, and health status pill |
| `components/OverviewDashboard.tsx` | Overview page state, parallel forecast fetching, and grid layout |
| `components/OverviewKpis.tsx` | 3-column system summary KPI tiles |
| `components/StationCard.tsx` | Station card with P50 sparkline, peak power, energy, and link to station page |
| `components/StationMap.tsx` | Overview map of Thailand: status markers, hover/focus tooltip, card highlight sync, list of plants without coordinates |
| `lib/thailandMap.ts` | Generated: pre-projected Thailand and neighbour outlines (Natural Earth, public domain) and `projectToMap(lon, lat)` |
| `scripts/gen_thailand_map.py` | Regenerates `lib/thailandMap.ts` (run only if the map window or source data changes) |
| `components/Sparkline.tsx` | Pure SVG area sparkline with gradient fill |
| `components/StationDashboard.tsx` | Station page state controller, query param synchronization, and 12-col layout |
| `components/StationHeader.tsx` | Station subheader with back link, capacity, and previous/next day date picker |
| `components/StationKpis.tsx` | 3-column station KPI tiles (energy, peak power with time, peak/capacity ratio) |
| `components/ForecastChart.tsx` | SVG generation chart with mouse hover and touch drag scrub support |
| `components/StatusPanel.tsx` | 4-column side panel with forecast metadata, alert triggers, and download buttons |
| `components/StatusBadge.tsx` | Status pill badges with symbols and text (`ready`, `stale`, `fallback`, `missing`, `error`) |
| `components/Alert.tsx` | Reusable error and warning alert banners |
| `components/DataTable.tsx` | Collapsible 96-row interval table with dimmed zero-generation night rows |
| `public/staticwebapp.config.json` | Static Web Apps routing; ignored by the storage website that hosts the dashboard now |

## Run locally

Requires Node.js ≥ 20.9 (tested with Node 20 & 22).

```bash
cd apps/web
npm ci                      # Install dependencies
cp .env.example .env.local  # Set NEXT_PUBLIC_API_BASE_URL (defaults to http://localhost:8000)
npm run dev                 # Starts dev server on http://localhost:3000
```

Start the backend API in demo mode (see `apps/api`):
```bash
cd apps/api
uv run uvicorn app.main:app --reload
```

## Check and build

Before committing or opening a PR, ensure all checks pass:

```bash
npm run lint        # ESLint 9 validation
npm run typecheck   # Next.js route typegen + tsc --noEmit
npm run build       # Static export -> out/
npx serve out       # Preview the production static export
```

## API contract used

- `GET /health` → `{"status": "ok", ...}` (polled every 60 s for the status pill)
- `GET /api/v1/plants` → `[{id, name, capacity_kw, lat, lon}, ...]`
- `GET /api/v1/forecast?plant_id=S01&date=YYYY-MM-DD` → `{plant_id, date, issued_at, model_version, forecast_mode, issue_scenario, unit, resolution_minutes, timezone, points: [{timestamp, p10, p50, p90} × 96]}`

Daily energy calculation = `Σ(p50) × resolution_minutes / 60` (i.e. `× 0.25` for 15-min intervals), in kWh (or MWh if $\ge$ 10,000 kWh).

## Deploy

`.github/workflows/deploy-web.yml` builds the site with `NEXT_PUBLIC_API_BASE_URL` = the `API_BASE_URL` variable
and uploads `out/` to the `$web` container of the storage account's static website (index `index.html`, error page
`404.html`). Every page is a real file, so no routing rules are needed. The website URL must be in the API's
`ALLOWED_ORIGINS`. Setup: `infra/azure/README.md`.

## Constraints of static export

- No Next.js API routes (`app/api/...`), server actions, or server-side rendering.
- `images.unoptimized: true` is configured in `next.config.ts`.
- Deep linking is achieved via client-side query parameters (`/station/?id=S01&date=YYYY-MM-DD`) wrapped in `<Suspense>` boundaries.
