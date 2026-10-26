# DESIGN.md: Solar Forecast Dashboard

The visual rules for `apps/web`. Read this before you build or restyle a component. If this file and a component
disagree, this file wins, so fix the component or change this file in the same PR.

> **Source.** This is adapted from *"Sistema de Monitoreo Eléctrico WattVision"* by
> [@groquispe100inf-max](https://designmd.ai/groquispe100inf-max/design-md-sistema-de-monitoreo-el-ctrico-wattvision)
> (MIT licence). The original targets home electricity *consumption* in Bolivia. We translated it and adapted it for
> day-ahead solar *generation* forecasts for PEA plants. [Changes from the original](#8-changes-from-the-original)
> lists what we changed.

## 1. Visual theme and atmosphere

The UI should feel **technically reliable** and **in control**, like a simplified Power BI or SCADA overview for grid
operators. It should not feel like a social app or a game. The main targets are a laptop (1280 px or wider) and a
tablet (768 px or wider). Phone width must still work, but it is not the main target.

- **Dark only.** We do not follow the OS light mode. Long data-reading sessions are easier on a dark background.
- Data is the hero. Chrome (headers, borders, labels) stays quiet and grey. Colour is for data and for status.
- No decorative imagery, gradients behind text, or animations beyond short hover and fade transitions (150 ms or less).

## 2. Colour palette

Define these once as CSS variables in `app/globals.css`. Components use only `var(--…)` and never hex codes.

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#121212` | Page background |
| `--surface` | `#1E1E1E` | Cards, panels, tiles |
| `--surface-hover` | `#252525` | Row or card hover |
| `--border` | `#2C2C2E` | Card borders, table row lines, chart grid lines |
| `--text` | `#FFFFFF` | Main text, KPI numbers |
| `--muted` | `#98989D` | Labels, axis text, secondary info |
| `--accent` | `#00E5FF` | **Forecast data**: P50 line, sparklines, main KPI, primary buttons, focus ring |
| `--band` | `rgba(0, 229, 255, 0.16)` | P10–P90 uncertainty band |
| `--ok` | `#32D74B` | Status: API online, forecast available, primary model |
| `--warn` | `#FFD60A` | Status: fallback model, stale forecast, partial data *(added, not in original)* |
| `--bad` | `#FF453A` | Status: API offline, forecast missing, error |
| `--bad-bg` | `#3A1C1C` | Alert box background |

Rules:

- Status colours (`--ok`, `--warn`, `--bad`) mean **status only**. Never use them to decorate a chart.
- Never show a status by colour alone. Always pair it with a text label or an icon, such as "● Online" or "⚠ Fallback".
- Do not use pastel colours or white or light backgrounds.

## 3. Typography

Load the fonts with `next/font/google`. It self-hosts them at build time, so the static export still works.

| Role | Font | Size / weight | Use |
|---|---|---|---|
| Title | Inter | 24 px / 600 | Page title (`h1`) |
| Section | Inter | 16 px / 600 | Card titles (`h2`) |
| Body | Inter | 14 px / 400 | Everything else |
| Label | Inter | 12 px / 500, `--muted`, uppercase, 0.04em tracking | Tile labels, table headers |
| KPI | JetBrains Mono | 32 px / 700 | Big numbers (kW, kWh, %) |
| Data | JetBrains Mono | 13 px / 400 | Table cells, timestamps, model version, chart readout |

Numbers always use the monospace font with `font-variant-numeric: tabular-nums`, so digits line up as they update.
Units sit after the number, smaller and `--muted`: **4,812** <small>kWh</small>.

## 4. Component styles

- **Cards / tiles**: `background: var(--surface)`, `border: 1px solid var(--border)`, `border-radius: 16px`,
  `padding: 20px`. No shadows.
- **Station card** (overview page): a whole card is one link. On hover, use `--surface-hover` and an `--accent`
  border. On keyboard focus, show a 2 px `--accent` outline.
- **Charts**: grid lines in `--border`, axis text in `--muted` at 12 px. P50 is a 2 px `--accent` line. P10–P90 is
  a `--band` area with no outline. No thick borders around the plot. Use an area style for the
  P50 sparkline on station cards (`--accent` to transparent gradient). The hover readout shows time and P10/P50/P90
  in the Data font.
- **Tables**: rows have `border-bottom: 1px solid var(--border)`, and a hovered row uses `--surface-hover`. Numbers
  are right-aligned.
- **Alerts**: `background: var(--bad-bg)`, `color: var(--bad)`, `border-left: 4px solid var(--bad)`,
  `border-radius: 8px`, `padding: 12px 16px`. A warning alert uses `--warn` with `rgba(255, 214, 10, 0.10)` as
  the background.
- **Status pill**: a small rounded pill with a coloured dot and a text label, e.g. `● API online`.
- **Buttons**: primary buttons have an `--accent` background with `#121212` text. Secondary buttons are transparent
  with a `1px solid var(--border)` border and `--text` text. Radius 8 px, height 36 px.
- **Inputs** (date picker, select): `--surface` background, `--border` border, radius 8 px, height 36 px, and an
  `--accent` focus ring.

## 5. Layout

- **Grid:** 12 columns, with a 24 px gutter on desktop and 16 px on mobile. Max content width is 1280 px, centred.
- **Spacing:** multiples of 8 px only (8, 16, 24, 32, 48).
- **Overview page (`/`)**: a KPI row of 3 tiles × 4 columns, then the station cards. Show 4 cards per row (3 columns
  each) at 1280 px or wider, 2 per row on tablets, and 1 per row on phones.
- **Station page (`/station/?id=S01`)**: a KPI row of 3 tiles × 4 columns. Below it, the main chart spans
  **8 columns** and the status/alerts panel spans **4 columns** on the right. Below 1024 px, the panel stacks under
  the chart. The data table spans all 12 columns at the bottom.

## 6. Icons

Use inline SVG icons only. Do not add an icon library just for a handful of icons. Pick icons that suit the domain:
a sun, a lightning bolt, a gauge, a solar panel or a clock. Do not use a generic light bulb.

## 7. Do's and don'ts

- ✅ Show the unit next to every number (kW for power, kWh for energy).
- ✅ Show the time zone once per page: "All times Asia/Bangkok (UTC+7)".
- ✅ Show the issue time and the forecast age wherever a forecast appears, so a stale forecast is obvious.
- ✅ Use area/band charts to show uncertainty, and keep P50 as a crisp line on top.
- ❌ Do not use white or pastel backgrounds or light mode.
- ❌ Do not use red or green for anything that is not a status.
- ❌ Do not show real PEA measurements (actual power) on any public page. See the
  [frontend requirements](../../docs/frontend-requirements.md#out-of-scope).

## 8. Changes from the original

| Original (WattVision) | Here | Why |
|---|---|---|
| Show Bolivianos (`Bs.`) next to kWh | Dropped; show kWh only | We have no tariff data, and a cost estimate would be misleading |
| Red alert for "vampire" consumption peaks | Red for API offline, missing or invalid forecast | We forecast generation, not consumption |
| `#30D158` green gradient under chart lines | Cyan band (`--band`) for P10–P90 | Green is reserved for status. The band shows uncertainty |
| No warning colour | Added `--warn` `#FFD60A` | Fallback and stale forecasts need a state between OK and error |
| Light/dark preview | Dark only | Matches the original "don't use white backgrounds" rule and halves the CSS |
| Dashboard: 3 KPIs, 8-col chart, 4-col alerts | Kept for the station page; added an overview page with station cards | Several plants need a list → detail flow |

<details>
<summary>Original licence (MIT)</summary>

The original design text is © its author ([@groquispe100inf-max](https://designmd.ai/groquispe100inf-max)) and is
published on designmd.ai under the MIT licence, which allows use, copying and modification with attribution.
</details>
