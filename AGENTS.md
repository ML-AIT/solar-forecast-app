# AGENTS.md — solar-forecast-app

Rules for team members and AI coding agents working in this repo.

## Scope

This repo holds only the **serving side**: the FastAPI API (`apps/api`), the Next.js dashboard (`apps/web`), Azure
infrastructure notes and CI/CD. Data processing and model training live in the ML repo (`Solar_Power_Prediction`).
The interface between the two is the **forecast JSON schema** in `apps/api/README.md`. Change it only with PRs to both repos.

## Hard rules

1. **No secrets in git.** Azure credentials go in GitHub environment variables and secrets; local config goes in `.env` (gitignored).
2. **No real PEA plant data in this repo.** It is confidential. Tests and demo mode use synthetic data only.
3. **Keep it simple.** No database, auth system, server-side rendering, Next.js API routes or extra services
   unless the team agrees in a decision record. See `docs/architecture.md`.
4. **The API contract is stable.** Changing a response shape means updating `apps/api` tests, `apps/web/lib/api.ts`
   and the docs in the same PR.
5. **`main` is always deployable.** Merge only through a reviewed PR with green CI.

## Conventions

| Area | Convention |
|---|---|
| Python | 3.12, uv (commit `uv.lock`), ruff (format + lint, line length 100), type hints, pydantic v2 schemas, settings via env vars (`app/config.py`) |
| TypeScript | strict mode, ESLint, API types in `apps/web/lib/api.ts`, no `any` |
| Time | All timestamps are ISO 8601 with offset, Asia/Bangkok (`+07:00`). 96 points per day, interval-start labelled |
| Units | Power in kW; energy in kWh (= Σ p50 × 0.25 h) |
| Branches | `feat/`, `fix/`, `infra/`, `docs/`, then a PR into `main` and a squash merge (or a merge commit to keep meaningful commits) |
| Commits | Imperative mood, explain *why*. **No AI co-author / "Generated with" trailers** |

## Working procedure for AI agents

1. Read README.md, this file and `docs/architecture.md` before editing.
2. For any non-trivial change, state the plan first: the goal, the files and how you will verify it.
3. Make small, focused diffs and avoid unrelated refactors.
4. Write or update tests first for API behaviour.
5. Verify before claiming done:
   - API: `cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
   - Web: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`

   Report the real output, and say so if you could not run something.
6. Keep the docs in sync: README, API docs, `infra/azure/README.md`.
7. Git safety: work on a branch, never force-push `main`, and never commit `.env`.
