# Resuming the resale app build

Last updated 2026-10-18. Everything is on branch `ccr-3346e419-qz127p` of `unklefunk/housemusicswarm-` (draft PR open against `main`).

## Pick it up on the Mac Studio

```bash
git fetch origin ccr-3346e419-qz127p
git checkout ccr-3346e419-qz127p
python3 -m venv .venv-resale && source .venv-resale/bin/activate
pip install -r resale_app/requirements-dev.txt
python -m pytest resale_app/tests          # should be all green
python -m resale_app demo                  # look around: http://127.0.0.1:8090
```

When you're ready for real data: `cp` your inventory to a CSV (columns at the top of `resale_app/seed.py`), run `python -m resale_app seed --file your.csv`, put `ANTHROPIC_API_KEY` in `resale_app/.env`, and `python -m resale_app serve`.

## State: Phase 1 core is built

| Piece | State |
|---|---|
| SQLite schema: items, photos, analyses, per-platform listings | Done, tested |
| Seed script (CSV, idempotent) | Done, tested. **The bundled CSV is a sample. Your real preloaded inventory still needs to be supplied.** |
| Phone upload page (many photos, new or existing item) + JSON API | Done, tested, checked at phone width |
| Drop-folder ingest + polling watcher + Hazel rule description and script | Done, tested. Hazel itself untried. |
| Vision step (identify, labels, flaws, photo tags, suggested grade) | Done. Live path tested with a fake client and through the real SDK with mocked HTTP. **Never run against the live API.** |
| Listing drafts per platform, honesty guards, voice linter | Done, tested |
| Missing-photo prompts per category | Done, tested |
| Review cards (approve / edit / skip, redraft, not-applicable) | Done, tested |
| Export packs (page with copy buttons, txt, zip with photos in order) | Done, tested |
| Demo mode + demo data | Done |

120 tests pass (`python -m pytest resale_app/tests`, about 20 seconds, no network).

## Decisions to revisit

- **The original build plan was not available** (the shared chat link couldn't be read), so Phase 1 was built from the written spec only. Anything the plan said that the spec didn't, such as categories beyond boards, clothing and sneakers, other platforms, or pricing, is not here. Compare this against the plan.
- **Platforms:** eBay, Mercari, Facebook Marketplace, Poshmark (clothing and sneakers only). Add or change them in `platforms.py`. Limits there are from memory.
- **Models:** `claude-opus-5-5` for both steps. `claude-sonnet-5-5` is the cheaper option; compare quality on real items first.
- **No server-side refusal fallback** is enabled on the Claude calls. A refusal is shown on the item with a retry button. Add Anthropic's `fallbacks` option if refusals turn out to be a real nuisance.
- **Single worker thread**, SQLite in WAL mode, no auth beyond an optional shared token. Fine for one seller on a home network.

## Suggested next steps

1. First real run in live mode on 3 to 5 items. Read every card critically and fix prompts in `vision.py` / `voice.py` / `categories.py` from what it gets wrong.
2. Load the real inventory CSV and check the statuses.
3. Try the Hazel rule and correct `docs/HAZEL.md` where the wording differs.
4. Phase 2 candidates: price suggestions from sold comps, profit tracking from `cost_basis_cents`, posting helpers (the pack is already ordered for upload), a sold/relist workflow, measurements capture for clothing.
