# apps/web — Solar Forecast Dashboard (Next.js)

A single-page dashboard that shows the day-ahead 15-minute PV power forecast
(P50 line with P10–P90 band) for each PEA plant. It is a **static site**: Next.js
builds plain HTML/JS/CSS into `out/`, and the browser fetches data from the
FastAPI backend (`apps/api`).

> **Building the next version?** The plan is a station overview page (`/`) plus a station monitoring page
> (`/station/?id=S01`). Requirements and tickets are in [docs/frontend-requirements.md](../../docs/frontend-requirements.md),
> and the visual rules (dark theme, tokens, fonts, layout) are in [DESIGN.md](DESIGN.md).

## Stack

- Next.js 16 (App Router, `output: "export"`), React 19, TypeScript, ESLint 9
- Plain CSS (global variables in `app/globals.css` + CSS modules); light/dark follows the OS
- Chart is a small hand-written SVG (`components/ForecastChart.tsx`) — no chart library

## Files you will touch most

| File | What it does |
|---|---|
| `lib/api.ts` | API base URL, TypeScript types, and all `fetch` calls |
| `lib/format.ts` | Date/number helpers (Bangkok "tomorrow", HH:MM, number format) |
| `components/Dashboard.tsx` | The page: selectors, data loading, tiles, metadata |
| `components/ForecastChart.tsx` | SVG chart (P50 line, P10–P90 band, hover readout) |
| `components/StatTile.tsx` | One summary tile |
| `app/globals.css` | Colour variables (light + dark) |
| `public/staticwebapp.config.json` | Azure Static Web Apps routing (copied into `out/`) |

## Run locally

Requires Node.js ≥ 20.9 (tested with Node 24).

```bash
cd apps/web
npm ci                      # or `npm install` the first time
cp .env.example .env.local  # then edit if your API is not on localhost:8000
npm run dev                 # http://localhost:3000
```

Start the backend too (see `apps/api`). The FastAPI app must allow CORS from
`http://localhost:3000` (and from the deployed Static Web Apps URL), otherwise the
browser blocks the requests and the dashboard shows "API offline".

## Environment variables

| Name | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI base URL, no trailing slash |

`NEXT_PUBLIC_*` values are **baked into the JavaScript at build time**. Changing
them on the hosting side after the build has no effect — rebuild instead.

## Check and build

```bash
npm run lint        # ESLint
npm run typecheck   # next typegen + tsc --noEmit
npm run build       # static export -> out/
npx serve out       # optional: preview the built site
```

## API contract used

- `GET /health` → `{"status": "ok", ...}` (polled every 60 s for the status pill)
- `GET /api/v1/plants` → `[{id, name, capacity_kw, lat, lon}, ...]`
- `GET /api/v1/forecast?plant_id=S01&date=YYYY-MM-DD` → `{plant_id, date, issued_at, model_version, unit, resolution_minutes, timezone, points: [{timestamp, p10, p50, p90} × 96]}`

Daily energy tile = `sum(p50) × resolution_minutes / 60` (i.e. `× 0.25` for 15-min data), in kWh.

## Deploy to Azure Static Web Apps (free tier)

1. Azure Portal → **Static Web Apps** → Create → plan **Free**, source **GitHub**, pick the repo/branch.
2. Build details: preset **Custom** (or Next.js), with
   - App location: `apps/web`
   - Api location: *(empty — the API is hosted separately)*
   - Output location: `out`
3. Azure commits a workflow under `.github/workflows/`. Set the API URL for the build step, e.g.

   ```yaml
   - uses: Azure/static-web-apps-deploy@v1
     with:
       app_location: "apps/web"
       output_location: "out"
       api_location: ""
     env:
       NEXT_PUBLIC_API_BASE_URL: ${{ vars.API_BASE_URL }}
   ```

   Alternatively build yourself (`npm ci && npm run build`) and deploy the prebuilt
   folder with `app_location: "apps/web/out"` and `skip_app_build: true`.
4. Add the Static Web Apps URL to the FastAPI CORS allow-list.

`staticwebapp.config.json` (in `public/`, so it ends up in `out/`) sets a
`navigationFallback` to `/index.html` and serves `404.html` for unknown paths.

## Constraints of static export

- No API routes (`app/api/...`), no server actions, no request-time server fetching.
- `next/image` optimisation is disabled (`images.unoptimized: true`).
- All data loading happens in client components (`"use client"`).
