# Resources

*APIs, tools, services, and infrastructure. Updated by nightly consolidation.*

---

## Agency Swarm Framework

- **Version:** 1.0.0
- **Docs:** https://agency-swarm.ai
- **Install:** `pip install agency-swarm`
- **Key pattern:** Agents communicate via `transfer_to_<agent_name>` handoff tools
- **Config:** `pyproject.toml`, `requirements.txt`

## OpenAI

- **API key env var:** `OPENAI_API_KEY`
- **Used for:** Assistants API backing all agents
- **Models:** See `shared_instructions.md` for available models note
- **Notes:** Heartbeats added to avoid tool timeouts (`helpers.py`)

## Composio

- **Purpose:** 10,000+ external integrations (Gmail, Calendar, Slack, etc.)
- **Auth:** `ManageConnections` tool inside agents
- **Key toolkits:** GMAIL, GOOGLECALENDAR, SLACK, NOTION, GITHUB, GOOGLEDRIVE
- **Pattern:** SearchTools → FindTools (include_args=True) → ExecuteTool or ProgrammaticToolCalling

## GitHub

- **Repo:** unklefunk/housemusicswarm-
- **Main branch:** `main`
- **Dev branch convention:** `claude/<feature-name>`
- **MCP access:** mcp__github__ tools available in Claude Code sessions

## Docker

- **Config:** `Dockerfile`, `docker-compose.yml`
- **Ignore:** `.dockerignore`
- **Notes:** Container build support for deployment

## Environment Variables

See `.env.example` for the full list. Key vars:

| Var | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required — all agents |
| *(add others as discovered)* | |

---

## Resource Template

```markdown
## Service Name

- **Purpose:** ...
- **Env var / auth:** ...
- **Key endpoints / tools:** ...
- **Notes:** ...
```

