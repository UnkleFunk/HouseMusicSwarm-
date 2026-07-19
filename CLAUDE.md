# HouseMusicSwarm — Codebase Guide

HouseMusicSwarm is a fork of **OpenSwarm**, a production-ready multi-agent AI system built on Agency Swarm v1.9.7+. It is customized for Unkle Funk (Glenn Giles), a Chicago house music DJ/producer, with a running artist website at unklefunk.music, a nightly Ableton co-writer, a reference-track finder, and a taste-driven music curation engine (Phase 2, in progress).

**Stack**: Python 3.12+ (Dockerfile uses 3.13-slim), Agency Swarm framework, OpenAI/Anthropic/Google via LiteLLM, Composio for external integrations, FastAPI for the API server(s), Node/Bun only for packaging the `openswarm` CLI binary.

---

## Directory Layout

```
HouseMusicSwarm-/
├── swarm.py                   # Agency factory — wires all 10 agents together
├── config.py                  # Model selection helpers (get_default_model, is_openai_provider)
├── helpers.py                 # Composio client utilities
├── run_utils.py                # Bootstrap + CLI entry point (auto-installs deps)
├── onboard.py                  # Interactive setup wizard (writes .env; auto-launched when no provider key is found)
├── server.py                   # FastAPI entry point for the main agency (python server.py → port 8080)
├── reference_finder_server.py  # Standalone FastAPI server for the Reference Finder UI/API (port 8081)
├── shared_instructions.md     # Runtime rules shared across all agents
├── pyproject.toml              # Python dependencies (entry: openswarm)
├── requirements.txt / requirements-dev.txt  # Pip-compatible deps mirror
├── package.json / package-lock.json  # npm packaging metadata for the `openswarm` CLI binary
├── Dockerfile / docker-compose.yml   # Containerized run (LibreOffice, Poppler, Playwright deps baked in)
├── .env.example                # Environment variable template
│
├── orchestrator/               # Agent 1: Router/coordinator (no tools)
├── virtual_assistant/          # Agent 2: 25+ tools — email, calendar, file ops, Slack
├── deep_research/               # Agent 3: Web + Scholar research, high reasoning
├── data_analyst_agent/          # Agent 4: IPython analysis, visualization, Composio
├── slides_agent/                 # Agent 5: HTML → PPTX, 30+ tools
├── docs_agent/                   # Agent 6: HTML → PDF/DOCX, document versioning
├── image_generation_agent/       # Agent 7: Gemini/GPT image generation + editing
├── video_generation_agent/       # Agent 8: Veo/Sora/Seedance video generation
├── reference_finder_agent/       # Agent 9: audio capture + reference-track matching for mixing/mastering
├── ableton_dream_agent/          # Agent 10: nightly Ableton Live Extension song-sketch generator
│
├── shared_tools/                # Cross-agent Composio utilities (auto-loaded)
├── patches/                     # Agency Swarm / dependency patches (most applied in swarm.py)
├── knowledge/                    # Persistent knowledge base (music_context.md, agent lessons, profiles, logs)
├── scripts/                      # Utility scripts (consolidate_knowledge.py, save_insight.sh)
├── music_curation/                # Phase 2 taste-scoring engine (profile.yaml, scoring.py, discovery.py — standalone, not yet agent-wired)
├── ableton_extensions/             # Ableton Live Extensions SDK context, taste fingerprint, built extension projects
├── supabase/                       # SQL schema backing the website's WIP-feedback / Q&A widget
├── website/                        # Static SPA for unklefunk.music (HTML/CSS/JS)
├── assets/                         # Static assets
├── bin/                            # `openswarm` CLI launcher script (npm bin entry)
└── .github/workflows/               # CI/CD (deploy-hostinger.yml, diagnose.yml, build-tui.yml, test-mac.yml)
```

---

## The 10 Agents

Each agent lives in its own folder with a consistent structure:
```
agent_name/
  __init__.py          # from .agent_name import create_agent_name
  agent_name.py         # Agent factory function create_<agent_name>()
  instructions.md        # System prompt for this agent
  tools/                  # Auto-loaded custom tools (BaseTool subclasses)
```

### 1. Orchestrator (`orchestrator/`)
**Role**: Entry point and router only — never executes tasks itself.

- Routes tasks to specialists via `SendMessage` (parallel) or `Handoff` (single specialist — prefer this)
- Has no tools; uses routing logic exclusively
- Key rule: if only one specialist needed, always `Handoff` so the specialist gets full conversation context

### 2. Virtual Assistant (`virtual_assistant/`)
**Role**: Executive assistant for productivity and administrative tasks.

- 25+ tools in `tools/`: `DraftEmail`, `ReadEmail`, `SendDraft`, `DeleteDraft`, `FindEmails`, `CreateCalendarEvent`, `CheckEventsForDate`, `RescheduleCalendarEvent`, `DeleteCalendarEvent`, `ReadFile`, `WriteFile`, `EditFile`, `ListDirectory`, `SendSlackMessage`, `ReadSlackMessages`, `CheckUnreadSlackMessages`, `GetSlackUserInfo`, `AddLabelToEmail`, `RemoveLabelFromEmail`, `ManageLabels`, `ProductSearch`, `ScholarSearch`, `GetCurrentTime`, `ListSkills`
- Also has `WebSearchTool`, `PersistentShellTool`, `IPythonInterpreter`, and Composio shared tools
- Model: medium reasoning (extended if OpenAI provider)

### 3. Deep Research Agent (`deep_research/`)
**Role**: Thorough evidence-based research with citations.

- Tools: `WebSearchTool`, `ScholarSearch`, `IPythonInterpreter`
- Model: HIGH reasoning effort
- Output format: executive summary → key findings → evidence → options → recommendation → risks
- Minimum 3–5 different search queries per request

### 4. Data Analyst (`data_analyst_agent/`)
**Role**: Data analysis, KPI tracking, visualization, business intelligence.

- Tools: `IPythonInterpreter`, `PersistentShellTool`, `WebSearchTool`, `LoadFileAttachment`, Composio shared tools
- Libraries available: pandas, numpy, scipy, scikit-learn, statsmodels, matplotlib, seaborn, plotly
- Outputs to `./mnt/outputs/`
- `test_files/` contains sample datasets for validation

### 5. Slides Agent (`slides_agent/`)
**Role**: Professional presentation creation via HTML → PPTX pipeline.

- 30+ tools in `tools/`: `InsertNewSlides`, `ModifySlide`, `DeleteSlide`, `ManageTheme`, `SlideScreenshot`, `ReadSlide`, `CheckSlide`, `CheckSlideCanvasOverflow`, `BuildPptxFromHtmlSlides`, `RestoreSnapshot`, `CreatePptxThumbnailGrid`, `ImageSearch`, `GenerateImage`, `DownloadImage`, `EnsureRasterImage`, plus `IPythonInterpreter`, `PersistentShellTool`, `WebSearchTool`
- Output path: `./mnt/<project_name>/presentations/` (HTML slides + `_theme.css` + `assets/` + `.pptx`)
- `pptx/` folder contains HTML-to-PPTX conversion libraries
- Instructions are 27KB — the most detailed in the codebase

### 6. Docs Agent (`docs_agent/`)
**Role**: Professional document creation and format conversion (HTML as canonical source).

- Tools: `CreateDocument`, `ViewDocument`, `ModifyDocument`, `ConvertDocument`, `ListDocuments`, `RestoreDocument`
- Also: `WebSearchTool`, `IPythonInterpreter`, `CopyFile`
- Output path: `./mnt/<project_name>/documents/`
- `files/` folder for document project storage
- Converts HTML → DOCX (auto), PDF, Markdown, TXT

### 7. Image Generation Agent (`image_generation_agent/`)
**Role**: Image generation, editing, composition, and background removal.

- Tools: `GenerateImages`, `EditImages`, `CombineImages`, `RemoveBackground`
- Models: `gemini-2.5-flash-image` (default), `gemini-3-pro-image-preview` (precision), `gpt-image-1.5` (when requested)
- Mandatory QC checklist after generation (composition, scale, lighting, artifacts)

### 8. Video Generation Agent (`video_generation_agent/`)
**Role**: Video generation, editing, and assembly.

- Tools: `GenerateVideo`, `EditVideoContent`, `TrimVideo`, `EditAudio`, `CombineVideos`, `AddSubtitles`, `GenerateImage`, `EditImage`, `CombineImages`, `LoadFileAttachment`
- Models: `veo-3.1` (default, Google), `sora` (OpenAI, highest fidelity), `seedance-1.5-pro` (ByteDance, budget)
- Strategy: text-to-video for generic scenes; image-to-video for branded/continuity needs

### 9. Reference Finder Agent (`reference_finder_agent/`)
**Role**: Finds high-quality current reference tracks (Beatport/Traxsource chart-toppers) to compare against a work-in-progress mix or master.

- Tools: `ListAudioDevices`, `CaptureAudio`, `ExtractFeatures`, `SearchReferences`, `FormatResults`, `BuildDatabase`
- Workflow: list devices → capture 30–60s → extract a weighted feature vector (low-end, tonal balance, dynamics, timbre) → search the local reference DB → format a spectrum-overlay comparison against the top 3 matches
- Genre focus: House, Deep House, Tech House, Funky/Minimal
- Ships its own standalone FastAPI server (`reference_finder_server.py`, port 8081) and `audio_utils.py` helper module, separate from the main agency server
- Boundary: only 30–90s previews for personal reference use, never full copyrighted tracks

### 10. Ableton Dream Agent (`ableton_dream_agent/`)
**Role**: Generates one new Ableton Live Extension song-sketch (TypeScript) per night in Unkle Funk's sonic identity — a creative collaborator, not a generic music assistant.

- Tools: `DreamSongSketch` (writes the `.ts` sketch + idea `.md` + updates `src/index.ts`), `SaveFeedback`, `ListSketches`
- Grounded in `knowledge/music_context.md` (taste DNA) and `ableton_extensions/taste_fingerprint.json` (measured audio-feature fingerprint from 139 analyzed favorites)
- Targets the Ableton Extensions SDK — see `ableton_extensions/sdk_context.md` for the TypeScript API reference (transactions, `MidiClip`, note timing in beats, track colors)
- Feedback loop: checks recent `ListSketches` ratings before generating each night; leans into elements Glenn rated highly, avoids patterns he rejected
- Model: latest Claude, Opus preferred for creative depth

---

## Communication Architecture

`swarm.py` applies 4 patches then builds the agency with two communication layers:

**Hub-and-spoke**: Orchestrator → any specialist via `SendMessage`
**Full mesh**: Any agent → any other agent via `Handoff`

```python
# Simplified view of swarm.py
all_agents = [orchestrator, virtual_assistant, slides_agent, deep_research,
              data_analyst, docs_agent, video_generation_agent,
              image_generation_agent, reference_finder, ableton_dream_agent]

send_message_flows = [(orchestrator, specialist, SendMessage) for specialist in all_agents if specialist is not orchestrator]
handoff_flows = [(a > b, Handoff) for a in all_agents for b in all_agents if a is not b]
```

- `SendMessage` = parallel delegation (orchestrator waits, collects, synthesizes)
- `Handoff` = full-context transfer (user iterates directly with specialist; prefer this for single-agent tasks)

**Patches applied at the top of `swarm.py`** (from `patches/`):
- `patch_utf8_file_reads.py` — UTF-8 encoding compatibility
- `patch_agency_swarm_dual_comms.py` — enables both SendMessage and Handoff simultaneously
- `patch_file_attachment_refs.py` — file reference tracking across tool calls
- `patch_ipython_interpreter_composio.py` — Composio context in IPython sessions

`patches/dom-to-pptx+1.1.5.patch` is a separate patch-package-style fix for the `dom-to-pptx` JS dependency used by the Slides Agent's HTML→PPTX pipeline; it is not applied via `swarm.py`.

---

## Key Conventions

### Adding a New Agent

1. Create the folder structure:
   ```
   agent_name/
     __init__.py
     agent_name.py         # def create_agent_name() -> Agent
     instructions.md
     tools/
   ```
   Use `agency-swarm create-agent-template` CLI helper.
2. Register in `swarm.py`: import `create_agent_name`, instantiate, add to `all_agents` (both `send_message_flows` and `handoff_flows` derive from that list automatically).
3. See `.cursor/rules/agency-swarm-workflow.mdc` for the full step-by-step process.
4. Default model: `get_default_model()` from `config.py`.

### Adding a New Tool

- Prefer MCP servers over custom tools (see `.cursor/commands/add-mcp.md`)
- Custom tool: subclass `BaseTool`, define Pydantic fields, implement `run() -> str`
- Drop `.py` in `agent_name/tools/` — auto-loaded by the framework
- Cross-agent tools go in `shared_tools/` and are imported explicitly in agent `.py` files

### Model Selection

- `DEFAULT_MODEL` env var sets the default (e.g., `gpt-5.2` or `anthropic/claude-sonnet-4-6`)
- OpenAI models: no slash (`gpt-5.2`, `o3`)
- LiteLLM-routed models: slash prefix (`anthropic/claude-sonnet-4-6`, `litellm/gemini/gemini-3-flash`)
- `config.py::is_openai_provider()` gates OpenAI-specific features (reasoning effort, etc.)

### Output Paths

| Agent | Output path |
|-------|-------------|
| Slides Agent | `./mnt/<project_name>/presentations/` |
| Docs Agent | `./mnt/<project_name>/documents/` |
| Data Analyst | `./mnt/outputs/` |
| Image/Video Agents | `./mnt/<project_name>/` |
| Ableton Dream Agent | Ableton Extensions project under `ableton_extensions/built/` |

### Composio Tool Discovery Pattern

When an agent needs external integrations:
```
ManageConnections → SearchTools → FindTools → ExecuteTool
```

---

## Environment Setup

```bash
cp .env.example .env   # fill in keys, or let the onboarding wizard write it
python run_utils.py    # or: openswarm
# run_utils.py bootstraps venv, installs deps, downloads TUI binary automatically
# onboard.py is auto-launched by run.py when no provider key is found (interactive wizard)
python server.py                    # FastAPI entry point — main agency, port 8080
python reference_finder_server.py   # standalone Reference Finder UI/API — port 8081
docker-compose up                   # containerized run (mounts ./mnt and ./uploads)
```

**Required** (pick one): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`

**Optional**:
| Variable | Purpose |
|----------|---------|
| `DEFAULT_MODEL` | Override default model (e.g., `gpt-5.2`) |
| `COMPOSIO_API_KEY` + `COMPOSIO_USER_ID` | 10,000+ external integrations |
| `SEARCH_API_KEY` | Web search + Scholar search (SearchAPI.io); also the planned discovery route for Traxsource/Beatport in `music_curation/` |
| `FAL_KEY` | Seedance video, video editing, background removal |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` / `UNSPLASH_ACCESS_KEY` | Stock photos |
| `GOOGLE_API_KEY` | Gemini image gen (Gemini 2.5 Flash) + Veo video |

---

## Website (Separate Concern)

`website/` contains a standalone static SPA for unklefunk.music:
- `index.html` — single-page artist hub: SoundCloud/Spotify embeds, podcast, releases, a self-hosted-audio WIP player, and a Supabase-backed Q&A/comments widget
- `style.css` — dark theme (AMOLED black `#09090b` bg, sky-blue `#3BA7E0` accents — see `STATUS.md` for the palette's revision history)
- `main.js` — canvas equalizer animation, mobile nav, scroll reveals, WIP player + Q&A widget logic
- `.htaccess` — gzip compression + browser caching headers
- `supabase/wip_feedback_schema.sql` — SQL schema backing the WIP-track feedback / Q&A widget

**Auto-deploy**: `.github/workflows/deploy-hostinger.yml` fires on push to `main` when `website/**` changes. SSH + SCP to Hostinger, targeting `~/domains/unklefunk.music/public_html/` (the legacy `~/public_html/` path exists but is NOT served by the domain — see `STATUS.md` for the incident history). No build step.

**Other workflows**:
- `diagnose.yml` — manual (`workflow_dispatch`) SSH check of the Hostinger web root, for debugging deploy issues
- `build-tui.yml` — builds the `openswarm` TUI CLI binaries (macOS arm64/x64, Linux, Windows) via Bun, triggered on `v*` tags or manually; publishes a GitHub Release
- `test-mac.yml` — smoke-tests the CLI packaging on macOS when `bin/openswarm`, `package.json`, or the build workflow changes

Always check `STATUS.md` first for the latest known-good state of the live site and any in-progress incident notes before touching deploy config.

---

## Phase 2: Music Curation & Ableton (In Progress)

The music curation and Ableton co-writing layer is defined in `VISION.md`. Current state:

### Built
- [x] `ableton_dream_agent/` — nightly Ableton Extension song-sketch generator, registered in `swarm.py`
- [x] `reference_finder_agent/` — audio capture + reference-track matching, registered in `swarm.py`
- [x] `ableton_extensions/` — SDK context (`sdk_context.md`), measured taste fingerprint (`taste_fingerprint.json`), analyzed-favorites CSVs (`analysis/`), built extension projects (`built/`), dated idea logs (`ideas/`)
- [x] `knowledge/music_context.md` — single authoritative taste/production-DNA source, read by every music-adjacent agent (enforced via `shared_instructions.md` §0)
- [x] `music_curation/` — taste-scoring engine skeleton: `profile.yaml` (hand-tuned weights, label tiers, artist seeds) and `scoring.py` (explainable scorer) are built and tested

### Not yet built (see `music_curation/README.md` for the full pipeline diagram and current blockers)
- [ ] `discovery.py` — polls Beatport + Traxsource for new candidates; **blocked** on picking an access route (SearchAPI.io key vs. Beatport partner API vs. RSS/label-page scraping — SearchAPI.io is the recommended starting point since a key is already available)
- [ ] `review_ui.py` — local Flask app for 30s-preview thumbs-up/down review, feeding `feedback.sqlite`
- [ ] `publish.py` — writes Beatport/Traxsource chart embed shortcodes into `website/index.html`, commits, pushes (chart rendering is handled entirely by their official embed widgets, not custom chart infra)
- [ ] `run_weekly.sh` — cron-driven discover → score → notify pipeline
- [ ] Wire `music_curation/` into `swarm.py` + orchestrator routing — it is currently a standalone module, not yet agent-wrapped

The learning loop (once discovery/review ship): every yes/no/maybe decision lands in `feedback.sqlite`; every 25 decisions, weights auto-retrain into `profile.learned.yaml`, leaving `profile.yaml` as a clean hand-tuned baseline (delete `profile.learned.yaml` to reset learning).

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `.cursor/rules/agency-swarm-workflow.mdc` | Primary guide for adding agents and tools |
| `.cursor/commands/add-mcp.md` | How to integrate MCP servers |
| `.cursor/commands/mcp-code-exec.md` | Code Execution Pattern (98% token reduction) |
| `.cursor/commands/write-instructions.md` | Effective agent instructions best practices |
| `.cursor/commands/create-prd.md` | PRD template for complex multi-agent systems |
| `shared_instructions.md` | Runtime rules shared by all agents (musical identity context, file delivery, Composio, agent roster) |
| `knowledge/music_context.md` | Authoritative Unkle Funk taste/production-DNA reference — read before any music- or creative-adjacent task |
| `music_curation/README.md` | Taste-scoring engine design, pipeline diagram, and current blockers |
| `VISION.md` | Music curation + Ableton Dreamer roadmap (Phase 2–3) |
| `STATUS.md` | Current live state of the project and website incident history |
| `AGENTS.md` | Generic upstream OpenSwarm customization guide (fork template); its agent list is stale relative to this file — treat this CLAUDE.md as authoritative for the current agent roster |
