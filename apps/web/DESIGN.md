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

- **Dark by default, light on request.** The header toggle cycles **Auto** (follows the OS) → **Light** → **Dark**,
  and the choice is saved in the browser (`lib/theme.ts`). A script in `<head>` applies it before the first paint,
  so a saved theme never flashes the other one.
- Data is the hero. Chrome (headers, borders, labels) stays quiet and grey. Colour is for data and for status.
- No decorative imagery, gradients behind text, or animations beyond short hover and fade transitions (150 ms or less).
  The one exception is the station map's day replay (§4): it only moves when someone presses play or drags the
  slider, and it shows forecast data, not decoration.

## 2. Colour palette

Define these once as CSS variables in `app/globals.css`. Components use only `var(--…)` and never hex codes.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#121212` | `#F4F6F9` | Page background |
| `--surface` | `#1E1E1E` | `#FFFFFF` | Cards, panels, tiles |
| `--surface-hover` | `#252525` | `#EDF1F5` | Row or card hover |
| `--border` | `#2C2C2E` | `#D8DEE6` | Card borders, table row lines, chart grid lines |
| `--text` | `#FFFFFF` | `#0F172A` | Main text, KPI numbers |
| `--muted` | `#98989D` | `#586273` | Labels, axis text, secondary info |
| `--accent` | `#00E5FF` | `#007C94` | **Forecast data**: P50 line, sparklines, main KPI, primary buttons, focus ring |
| `--band` | `rgba(0, 229, 255, 0.16)` | `rgba(0, 124, 148, 0.14)` | P10–P90 uncertainty band |
| `--ok` | `#32D74B` | `#1B7F3A` | Status: API online, forecast available, primary model |
| `--warn` | `#FFD60A` | `#946200` | Status: fallback model, stale forecast, partial data *(added, not in original)* |
| `--bad` | `#FF453A` | `#C8302B` | Status: API offline, forecast missing, error |
| `--ok-bg`, `--ok-border` | green at 12 % / 24 % | green at 10 % / 28 % | "Ready" badge |
| `--warn-bg`, `--warn-border` | yellow at 10 % / 25 % | amber at 10 % / 30 % | Warning alert and badge |
| `--bad-bg`, `--bad-border` | `#3A1C1C` / red at 30 % | `#FDECEB` / red at 30 % | Error alert and badge |
| `--on-accent` | `#121212` | `#FFFFFF` | Text on `--accent` buttons |
| `--accent-fade` | `--accent` at 0 % | `--accent` at 0 % | Transparent end of the sparkline gradient |
| `--inset` | white at 2 % | navy at 3 % | Empty-state boxes inside a card |
| `--code-bg` | black at 20 % | navy at 6 % | Inline `code` in alerts |
| `--map-night`, `--map-day`, `--map-dawn` | dark navy / teal / brown | grey-blue / pale blue / peach | Station map sky for the day replay |
| `--map-veil`, `--sunlight` | black / `#FFC24D` | navy / `#FFB020` | Night darkening and sunlight tint on the map |

The light values keep at least 4.5:1 contrast on `--surface` for text and status colours (yellow becomes amber).

Rules:

- `:root` holds the dark values and `color-scheme: dark`. The light values sit in `:root[data-theme="light"]` and,
  for Auto, in `@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) }`. Keep both light blocks
  identical. `color-scheme` follows the theme so native controls such as the date picker match.
- The chart grid uses `--border`. Remove the old `--grid` token and change `.grid` in `ForecastChart.module.css`
  to `var(--border)` in the same PR.
- Status colours (`--ok`, `--warn`, `--bad`) mean **status only**. Never use them to decorate a chart.
- Never show a status by colour alone. Always pair it with a text label or an icon, such as "● Online" or "⚠ Fallback".
- Do not use pastel colours. In light mode, white is for cards only; the page background is `--bg`.

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
  P50 sparkline on station cards (`--accent` to `--accent-fade` gradient). The hover readout shows time and P10/P50/P90
  in the Data font.
- **Station map** (overview page): hand-written SVG, no map library or tiles. Land is `--surface-hover` with a muted
  outline, neighbouring countries `--surface`, sea `--bg`. A marker is a status-coloured dot with a halo and a
  monospace label plus the status symbol (`S01 ⚠`), so the status never relies on colour alone. Hover or keyboard
  focus gives the marker an `--accent` ring, highlights the matching station card (and the reverse), and shows a
  tooltip card. Every marker is a link to the station page. Plants with no coordinates are listed under the map,
  never placed at a guessed position.
- **Day replay** (station map): a fleet P50 curve with a slider and a **Play the day** button sits under the map.
  The map shows one 15-minute slot at a time (the fleet peak until someone picks a time): a clock in the corner, the
  sky tinted from `--map-night` through `--map-dawn` to `--map-day`, and an `--accent` glow under each marker whose
  area grows with P50 ÷ capacity. Each marker also shows its P50 at that time. Play steps one slot every 110 ms from
  just before sunrise to just after sunset. The glow is `--accent`, never a status colour. The slider is a native
  range input with an `aria-valuetext` of the time and fleet P50, and `prefers-reduced-motion` turns the transitions off.
- **Tables**: rows have `border-bottom: 1px solid var(--border)`, and a hovered row uses `--surface-hover`. Numbers
  are right-aligned.
- **Alerts**: `background: var(--bad-bg)`, `color: var(--bad)`, `border-left: 4px solid var(--bad)`,
  `border-radius: 8px`, `padding: 12px 16px`. A warning alert uses `--warn` with `--warn-bg` as the background.
- **Status pill**: a small rounded pill with a coloured dot and a text label, e.g. `● API online`.
- **Buttons**: primary buttons have an `--accent` background with `--on-accent` text. Secondary buttons are transparent
  with a `1px solid var(--border)` border and `--text` text. Radius 8 px, height 36 px.
- **Inputs** (date picker, select): `--surface` background, `--border` border, radius 8 px, height 36 px, and an
  `--accent` focus ring.

## 5. Layout

- **Grid:** 12 columns, with a 24 px gutter on desktop and 16 px on mobile. Max content width is 1280 px, centred.
- **Spacing:** multiples of 8 px only (8, 16, 24, 32, 48).
- **Overview page (`/`)**: a KPI row of 3 tiles × 4 columns. Below it, the station cards span **8 columns** (2 per
  row) and the **station map** spans **4 columns** on the right. Below 1024 px the map stacks under the cards; on
  phones the cards are 1 per row.
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
- ❌ Do not use pastel backgrounds.
- ❌ Do not use red or green for anything that is not a status.
- ❌ Do not show real PEA measurements (actual power) on any public page. See the
  [frontend requirements](../../docs/frontend-requirements.md#5-out-of-scope-for-now).

## 8. Changes from the original

| Original (WattVision) | Here | Why |
|---|---|---|
| Show Bolivianos (`Bs.`) next to kWh | Dropped; show kWh only | We have no tariff data, and a cost estimate would be misleading |
| Red alert for "vampire" consumption peaks | Red for API offline, missing or invalid forecast | We forecast generation, not consumption |
| `#30D158` green gradient under chart lines | Cyan band (`--band`) for P10–P90 | Green is reserved for status. The band shows uncertainty |
| No warning colour | Added `--warn` `#FFD60A` | Fallback and stale forecasts need a state between OK and error |
| Light/dark preview | Dark by default, with a light theme and an Auto option | The dashboard is shown in bright rooms and on projectors, where dark pages wash out |
| Dashboard: 3 KPIs, 8-col chart, 4-col alerts | Kept for the station page; added an overview page with station cards | Several plants need a list → detail flow |

<details>
<summary>Original licence (MIT)</summary>

The original DESIGN.md is published on designmd.ai under the MIT licence:

```
MIT License

Copyright (c) 2026 @groquispe100inf-max (designmd.ai)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
</details>
