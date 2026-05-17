# Projects

*Updated by nightly consolidation. Add new projects using the template below.*

---

## HouseMusicSwarm

**Status:** Active — in development
**GitHub:** unklefunk/housemusicswarm-
**Branch:** `claude/knowledge-management-setup-bnIT5`

### Purpose
Multi-agent system built on Agency Swarm v1.0.0 for orchestrating AI agents across research, content, data analysis, and virtual assistant functions.

### Agents
| Agent | Role | Status |
|---|---|---|
| Orchestrator | Entry point / routing | Active |
| Virtual Assistant | Admin, email, calendar | Active |
| Deep Research | Evidence-based research | Active |
| Data Analyst | KPIs, charts, analysis | Active |
| Docs Agent | Document creation | Active |
| Slides Agent | PowerPoint generation | Active |
| Image Agent | Image generation | Active |
| Video Agent | Video generation | Active |

### Key Files
- `swarm.py` — agency entry point
- `shared_instructions.md` — instructions shared by all agents
- `knowledge/` — this knowledge management system
- `scripts/consolidate_knowledge.py` — nightly consolidation

### Open Items
- Knowledge management system (this PR)
- QA testing pass on all agents

### Notes
- Uses Composio for 10k+ external integrations
- All agents can transfer to any other agent directly

---

## Project Template

```markdown
## Project Name

**Status:** Active | Paused | Complete
**GitHub/Link:** ...

### Purpose
...

### Key Files
- ...

### Open Items
- ...

### Notes
- ...
```

