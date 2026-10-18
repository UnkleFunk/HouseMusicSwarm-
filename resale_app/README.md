# Resale app

Photos in, honest marketplace listing drafts out. Phase 1 core: a FastAPI + SQLite inventory, a phone upload page, a Hazel-compatible drop-folder watcher, a vision step that reads the item from its photos, per-platform listing drafts in a warm, plain, no-hype voice, review cards (approve / edit / skip), and copy-paste listing packs.

It lives in `resale_app/` inside the HouseMusicSwarm repo but is self-contained: it has its own requirements, data folder and tests, and nothing else in the repo imports it.

## Try it in two minutes (no API key)

```bash
cd HouseMusicSwarm-
python3 -m venv .venv-resale && source .venv-resale/bin/activate
pip install -r resale_app/requirements-dev.txt
python -m resale_app demo            # http://127.0.0.1:8090
```

`demo` builds a separate database of five made-up items with generated placeholder photos, runs them through the real pipeline, and serves the app. A banner on every page says that no model is looking at the photos. In demo mode the "vision" step reads what you typed and the photo **file names** (`socket.jpg`, `size_tag.jpg`, `soles.jpg`) instead of the pixels.

The demo data shows each review state: a clean item, an untested board, a board with a blurry socket photo and no serial sticker, and sneakers missing a box label.

## Using it for real (live mode)

```bash
export ANTHROPIC_API_KEY=sk-ant-...          # or put it in resale_app/.env
python -m resale_app serve                    # add --host 0.0.0.0 to reach it from your phone
```

With a key set, the app uses Claude. Without one it stays in demo mode. If you sign in with `ant auth login` instead of a key, set `RESALE_MODE=live`.

- **Models:** both steps default to `claude-opus-5-5`. For a cheaper pass set `RESALE_VISION_MODEL` and/or `RESALE_DRAFT_MODEL` to `claude-sonnet-5-5`. Check the result on a few of your own items before switching.
- **Cost control:** at most 12 photos per item go to the model (`RESALE_MAX_VISION_PHOTOS`), each downscaled to 1568 px. Photos are read once per item; editing details and pressing *Redraft* only makes a small text call. Seeding spends nothing unless you pass `--analyze`. Upload, the drop folder and Hazel **do** queue a read for each item (the point of them), so with the app running and a key set, dropping photos costs money; pass `--no-analyze` to `ingest` or `watch` to stop that.
- **Phone access:** the app listens on `127.0.0.1` by default. For your phone on the same Wi-Fi, run with `--host 0.0.0.0` and set `RESALE_ACCESS_TOKEN=<something long>`. Open `http://<mac-ip>:8090/?token=<that token>` once and the browser remembers it. Without a token, anyone on your network can use the app.

## Getting photos in

| Way | How |
|---|---|
| **Phone upload page** | `/upload`. Pick several photos at once, add them to a new or existing item, optionally add brand, model, what you paid, and notes. |
| **Drop folder** | Photos dropped in `~/ResaleDrop` are picked up by `python -m resale_app watch`, or by Hazel calling `python -m resale_app ingest`. Folder and file-name conventions are in `docs/HAZEL.md`, along with the ready-made Hazel rule. |
| **Script / Shortcut** | `curl -F files=@a.jpg -F files=@b.jpg -F category=board http://127.0.0.1:8090/api/upload` returns JSON (`sku`, `added`, `duplicates`, `errors`). Add `-F item_id=3` to add to an existing item. |
| **Seed your inventory** | `python -m resale_app seed --file my_inventory.csv`. Column reference is at the top of `seed.py`; `seed/sample_inventory.csv` is a **sample**, not your inventory. Re-running is safe. |

Identical photos are recognised by content and never added twice.

## What the pipeline does

1. **Read the photos** (vision step). Identify brand and model, read model numbers and every legible label line, list visible flaws (with the photo that shows each), tag each photo with what it shows (socket, tag, soles ...) and how usable it is (blurry, dark ...), and suggest a condition grade.
2. **Check what's missing** against the category checklist, computed in code from those photo tags:
   - **Boards:** whole board, **socket close-up**, **I/O**, **back**, **serial sticker** (plus RAM/PCIe slots and what's included as optional).
   - **Clothing:** front, back, **brand tag**, **size and care tag**, and **flaw close-ups** whenever a flaw was seen (plus fabric detail and measurements as optional).
   - **Sneakers:** side profile, **box label**, **soles**, **insoles** (plus heel, toe box, tongue label, pair as optional).
   A blurry photo of a required shot counts as missing and the prompt says "retake it". "Not applicable" clears a prompt; for a missing box or accessories the listing says so.
3. **Draft a listing per platform** (eBay, Mercari, Facebook Marketplace, and Poshmark for clothing and sneakers): title, description, item specifics, condition grade (with each platform's own dropdown wording), keywords, and the suggested photo order, trimmed to each platform's limits.
4. **Review.** Each draft is a card: approve, edit, or skip. Warnings (a title over the limit, hype wording) show on the card.
5. **Export.** `/export/<platform>` has copy buttons per field; `pack.zip` has the text plus the photos renamed `01_..., 02_...` in upload order. Mark a listing posted to take it out of the pack.

Item status moves `intake → needs_photos / review → approved → listed → sold` (or `skipped`). `needs_photos` means a required shot is still missing; you can still approve.

## The voice, and what keeps it honest

Drafts are written as the seller, first person, plain and warm, with no hype. The rules are in `voice.py`. Beyond the prompt, code enforces the ones that matter:

- Only the **Notes** you write are treated as confirmed. A board with no testing noted is **always** described as untested; one noted as not working is sold for parts. If you write "tested: boots to BIOS", the listing repeats exactly that.
- **Serial numbers** are recorded on the card but never reach a title, description or specs. **What you paid** is never sent to the model and is flagged if it appears in text.
- Hype wording, exclamation marks, emoji and ALL CAPS are flagged on the review card (they are warnings, not silent rewrites).
- If the model skips a platform, a plain template draft fills the gap rather than leaving it blank.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RESALE_MODE` | `live` if `ANTHROPIC_API_KEY` is set, else `demo` | `live` calls Claude; `demo` is offline |
| `RESALE_HOME` | `resale_app/data/` | Database and photos. Git-ignored. Web app, Hazel and watcher must share it. |
| `RESALE_DROP_DIR` | `~/ResaleDrop` | The drop folder |
| `RESALE_VISION_MODEL` / `RESALE_DRAFT_MODEL` | `claude-opus-5-5` | Models for the two steps |
| `RESALE_MAX_VISION_PHOTOS` | `12` | Photos sent to the model per item |
| `RESALE_SETTLE_SECONDS` | `45` | Wait after the last dropped photo before reading |
| `RESALE_BATCH_GAP_SECONDS` | `120` | Loose photos closer together than this become one item |
| `RESALE_ACCESS_TOKEN` | none | Require `?token=` (then a cookie) on every request |
| `RESALE_WORKER` | `1` | `0` disables the background worker (use `analyze` instead) |

Values are also read from `resale_app/.env` and the repo-root `.env`, without overriding real environment variables.

## Commands

```
python -m resale_app serve | demo | seed | ingest | watch | analyze | export
```

Run `python -m resale_app <command> --help` for options. `analyze` reads photos for queued items without the web app; `export <platform> --out DIR` writes a pack to disk.

## Tests

```bash
pip install -r resale_app/requirements-dev.txt
python -m pytest resale_app/tests
```

No network or key is needed. Live-mode code is tested two ways: against a fake Claude client, and through the real Anthropic SDK with its HTTP layer mocked (so the request shape and structured-output parsing are exercised).

## Known limits

- **Live mode has not made a real Claude call yet.** It was built and tested without an API key. The first real run is the real test; try it on two or three items and read the cards critically.
- **Platform limits** (title length, description length, photo counts, condition wording) are from memory of each marketplace's form and change over time. They're in `platforms.py`; check them.
- **Nothing is posted for you.** Export is copy-paste on purpose. Pricing suggestions, posting automation and profit tracking are not in Phase 1.
- The Hazel rule description (`docs/HAZEL.md`) was not tried in Hazel itself.
- Photos can't show whether electronics work or whether an item is authentic. The app never claims either.
- Concurrency: one worker reads one item at a time, which is plenty for one seller.
