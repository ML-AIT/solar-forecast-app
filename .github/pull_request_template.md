## What & why
<!-- 1–3 sentences. Link the Trello card. -->

## How verified
<!-- commands run + result, screenshots for UI changes -->

## Checklist
- [ ] No secrets / real plant data in the diff
- [ ] API: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` pass
- [ ] Web: `npm run lint && npx tsc --noEmit && npm run build` pass
- [ ] API contract unchanged, or updated in api tests + `apps/web/lib/api.ts` + docs
- [ ] Docs updated if setup/behaviour changed
