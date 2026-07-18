# HouseMusicSwarm — Codebase Guide

HouseMusicSwarm is a fork of **OpenSwarm**, a production-ready multi-agent AI system built on Agency Swarm v1.9.7+. It is customized for Unkle Funk, a Chicago house music DJ/producer, with a running artist website at unklefunk.music and a roadmap for AI-powered music curation (Phase 2).

**Stack**: Python 3.12+, Agency Swarm framework, OpenAI/Anthropic/Google via LiteLLM, Composio for external integrations.

---

## Directory Layout

```
HouseMusicSwarm-/
├── swarm.py                  # Agency factory — wires all 8 agents together
├── config.py                 # Model selection helpers (get_default_model, is_openai_provider)
├── helpers.py                # Composio client utilities
├── run_utils.py              # Bootstrap + CLI entry point (auto-installs deps)
├── shared_instructions.md    # Runtime rules shared across all agents
├── pyproject.toml            # Python dependencies (entry: openswarm)
├── requirements.txt          # Pip-compatible deps mirror
├── .env.example              # Environment variable template
│
├── orchestrator/             # Agent 1: Router/coordinator (no tools)
├── virtual_assistant/        # Agent 2: 25+ tools — email, calendar, file ops, Slack
├── deep_research/            # Agent 3: Web + Scholar research, high reasoning
├── data_analyst_agent/       # Agent 4: IPython analysis, visualization, Composio
├── slides_agent/             # Agent 5: HTML → PPTX, 30+ tools
├── docs_agent/               # Agent 6: HTML → PDF/DOCX, document versioning
├── image_generation_agent/   # Agent 7: Gemini/GPT image generation + editing
├── video_generation_agent/   # Agent 8: Veo/Sora/Seedance video generation
│
├── shared_tools/             # Cross-agent Composio utilities (auto-loaded)
├── patches/                  # Agency Swarm framework monkey-patches (applied in swarm.py)
├── knowledge/                # Persistent knowledge base (agent lessons, profiles, logs)
├── scripts/                  # Utility scripts (consolidate_knowledge.py, save_insight.sh)
├── website/                  # Static SPA for unklefunk.music (HTML/CSS/JS)
├── assets/                   # Static assets
└── .github/workflows/        # CI/CD (deploy-hostinger.yml, build-tui.yml)
```

---

## The 8 Agents

Each agent lives in its own folder with a consistent structure:
```
agent_name/
  __init__.py          # from .agent_name import create_agent_name
  agent_name.py        # Agent factory function create_<agent_name>()
  instructions.md      # System prompt for this agent
  tools/               # Auto-loaded custom tools (BaseTool subclasses)
```

### 1. Orchestrator (`orchestrator/`)
**Role**: Entry point and router only — never executes tasks itself.

- Routes tasks to specialists via `SendMessage` (parallel) or `Handoff` (single specialist — prefer this)
- Has no tools; uses routing logic exclusively
- Key rule: if only one specialist needed, always `Handoff` so the specialist gets full conversation context

### 2. Virtual Assistant (`virtual_assistant/`)
**Role**: Executive assistant for productivity and administrative tasks.

- 25+ tools in `tools/`: `DraftEmail`, `ReadEmail`, `SendDraft`, `CreateCalendarEvent`, `CheckEventsForDate`, `RescheduleCalendarEvent`, `DeleteCalendarEvent`, `ReadFile`, `WriteFile`, `EditFile`, `ListDirectory`, `SendSlackMessage`, `ReadSlackMessages`, `CheckUnreadSlackMessages`, `GetSlackUserInfo`, `AddLabelToEmail`, `RemoveLabelFromEmail`, `ProductSearch`, `ScholarSearch`, `GetCurrentTime`, `ListSkills`
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

---

## Communication Architecture

`swarm.py` applies 4 patches then builds the agency with two communication layers:

**Hub-and-spoke**: Orchestrator → any specialist via `SendMessage`
**Full mesh**: Any agent → any other agent via `Handoff`

```python
# Simplified view of swarm.py
send_message_flows = [(orchestrator, specialist) for specialist in all_specialists]
handoff_flows = [(a, b) for a in all_agents for b in all_agents if a is not b]
```

- `SendMessage` = parallel delegation (orchestrator waits, collects, synthesizes)
- `Handoff` = full-context transfer (user iterates directly with specialist; prefer this for single-agent tasks)

**Patches applied** (`patches/`):
- `patch_agency_swarm_dual_comms.py` — enables both SendMessage and Handoff simultaneously
- `patch_file_attachment_refs.py` — file reference tracking across tool calls
- `patch_ipython_interpreter_composio.py` — Composio context in IPython sessions
- `patch_utf8_file_reads.py` — UTF-8 encoding compatibility

---

## Key Conventions

### Adding a New Agent

1. Create the folder structure:
   ```
   agent_name/
     __init__.py
     agent_name.py        # def create_agent_name() -> Agent
     instructions.md
     tools/
   ```
   Use `agency-swarm create-agent-template` CLI helper.
2. Register in `swarm.py`: import `create_agent_name`, instantiate, add to communication flows.
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
- LiteLLM-routed models: slash prefix (`anthropic/claude-sonnet-4-6`, `google/gemini-2.5-flash`)
- `config.py::is_openai_provider()` gates OpenAI-specific features (reasoning effort, etc.)

### Output Paths

| Agent | Output path |
|-------|-------------|
| Slides Agent | `./mnt/<project_name>/presentations/` |
| Docs Agent | `./mnt/<project_name>/documents/` |
| Data Analyst | `./mnt/outputs/` |
| Image/Video Agents | `./mnt/<project_name>/` |

### Composio Tool Discovery Pattern

When an agent needs external integrations:
```
ManageConnections → SearchTools → FindTools → ExecuteTool
```

---

## Environment Setup

```bash
cp .env.example .env   # fill in keys
python run_utils.py    # or: openswarm
# run_utils.py bootstraps venv, installs deps, downloads TUI binary automatically
```

**Required** (pick one): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`

**Optional**:
| Variable | Purpose |
|----------|---------|
| `DEFAULT_MODEL` | Override default model (e.g., `gpt-5.2`) |
| `COMPOSIO_API_KEY` + `COMPOSIO_USER_ID` | 10,000+ external integrations |
| `SEARCH_API_KEY` | Web search + Scholar search (SearchAPI.io) |
| `FAL_KEY` | Seedance video, video editing, background removal |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` / `UNSPLASH_ACCESS_KEY` | Stock photos |
| `GOOGLE_API_KEY` | Gemini image gen (Gemini 2.5 Flash) + Veo video |

---

## Website (Separate Concern)

`website/` contains a standalone static SPA for unklefunk.music:
- `index.html` (918 lines) — single-page artist hub with SoundCloud/Spotify embeds, podcast, releases
- `style.css` (2199 lines) — dark/gold theme (`#09090b` bg, `#c9a84c` accent)
- `main.js` (501 lines) — canvas equalizer animation, mobile nav, scroll reveals
- `.htaccess` — gzip compression + browser caching headers

**Auto-deploy**: `.github/workflows/deploy-hostinger.yml` fires on push to `main` when `website/**` changes. SSH + SCP to Hostinger (`~/domains/unklefunk.music/public_html/`). No build step.

---

## Phase 2 Roadmap (Pending)

The music curation automation layer is defined in `VISION.md` but not yet implemented:

- [ ] `music_profile_agent/` — living taste DNA document (sub-genres, BPM 118–128, artist network)
- [ ] `SearchTraxsource` + `SearchBeatport` tools for new release discovery
- [ ] `music_curation_agent/` — discover, score, and rank tracks against taste profile
- [ ] `PublishChart` tool wired into Virtual Assistant → auto-update website
- [ ] Register new agents in `swarm.py` + update orchestrator routing
- [ ] Test with one month of Traxsource releases

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `.cursor/rules/agency-swarm-workflow.mdc` | Primary guide for adding agents and tools |
| `.cursor/commands/add-mcp.md` | How to integrate MCP servers |
| `.cursor/commands/mcp-code-exec.md` | Code Execution Pattern (98% token reduction) |
| `.cursor/commands/write-instructions.md` | Effective agent instructions best practices |
| `.cursor/commands/create-prd.md` | PRD template for complex multi-agent systems |
| `shared_instructions.md` | Runtime rules shared by all agents |
| `VISION.md` | Music curation roadmap (Phase 2–3) |
| `STATUS.md` | Current live state of the project |
| `AGENTS.md` | Quick reference table for all 8 agents |
