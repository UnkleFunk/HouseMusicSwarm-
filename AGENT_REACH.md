# Agent Reach — Optional Host-Level CLI Toolkit

[Agent Reach](https://github.com/Panniantong/agent-reach) is a third-party selector, installer, health-checker, and router for internet-access CLI tools (`yt-dlp`, `gh`, `twitter-cli`, `bili-cli`, `rdt-cli`, OpenCLI, `mcporter`, and more). It is **not** part of this codebase, **not** an MCP server, and **not** installed automatically by anything in this repo (`run_utils.py`, `onboard.py`, `docker-compose.yml`, etc. never touch it).

Think of it as an optional capability layer on the machine running the agency — useful when an agent needs to shell out for something WebSearchTool/Composio don't cover (e.g. pulling YouTube/Bilibili metadata, reading a GitHub repo via `gh`, fetching a page via Jina Reader).

## Install (host machine only, not this repo)

Agent Reach installs to `~/.agent-reach/` on whatever machine runs the agency — it is a per-machine, opt-in setup step the user runs themselves, not something baked into this project:

```bash
pipx install https://github.com/Panniantong/agent-reach/archive/main.zip
agent-reach install --env=auto
```

`--safe` (check only, no auto-install) and `--dry-run` (preview) flags are available if you want to review before it touches anything. See the [upstream install guide](https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md) for the full walkthrough, including optional channels (Twitter, Reddit, small red book, LinkedIn, etc.) that need user-provided cookies or API keys.

## Boundaries (carried over from upstream, apply here too)

- Never run `agent-reach`/upstream install commands with `sudo` without explicit user approval.
- Never modify system files outside `~/.agent-reach/`.
- Never install channels/packages the user didn't ask for.
- Never commit, log, or paste cookies, tokens, or API keys extracted for Agent Reach channels anywhere in this repo.
- Agents must not attempt to silently install Agent Reach on the user's behalf — it requires host-level package installs and, for several channels, handing over account cookies. Point the user at this file and the upstream guide instead and let them decide.

## Using it from an agent

Only `virtual_assistant`, `slides_agent`, and `data_analyst_agent` carry `PersistentShellTool`, so those are the agents that can shell out to Agent Reach's upstream tools. Before relying on any upstream command, check it's actually present on this host:

```bash
command -v agent-reach && agent-reach doctor
```

If it's missing, treat it as unavailable — do not try to install it inline. Fall back to the existing tools (`WebSearchTool`, `ScholarSearch`, Composio) instead.

| Need | Upstream tool (via shell) | Example |
|------|---------------------------|---------|
| Read a web page as clean text | Jina Reader | `curl -s "https://r.jina.ai/<URL>"` |
| YouTube video/track metadata | `yt-dlp` | `yt-dlp --dump-json <URL>` |
| GitHub repo/issue lookups | `gh` | `gh search repos "query"` |
| Bilibili search/details | `bili` | `bili search "query" --type video` |
| Exa web search | `mcporter` | `mcporter call 'exa.web_search_exa(...)'` |

## Relevance to this project

- `reference_finder_agent` could eventually use `yt-dlp`/`bili`-style lookups to cross-check candidate reference tracks, but this is not wired in — it stays a manual, host-shell option for now.
- `music_curation/discovery.py` (see `music_curation/README.md`) is still blocked on picking a Beatport/Traxsource access route; Agent Reach's Exa Search channel is a possible future input but is not part of the currently recommended SearchAPI.io path.
- Nothing here changes the website (`website/`), Supabase schema, or deploy workflows — those remain unrelated to Agent Reach.
