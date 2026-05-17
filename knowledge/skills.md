# Skills & Repeatable Patterns

*Techniques and workflows worth preserving across sessions. Updated by nightly consolidation.*

---

## Agency Swarm — Adding a New Agent

**When:** Need to add a specialized agent to the swarm

**Steps:**
1. Create `agent_name/` folder with `__init__.py`, `agent_name.py`, `instructions.md`
2. Add `tools/` subfolder if agent needs custom tools
3. Update `swarm.py` — import agent, add to `Agency` + `communication_flows`
4. Update `shared_instructions.md` agency roster table
5. Run qa-tester with 5 example queries

**Lessons:**
- Phase 1: agent-creator + instructions-writer in parallel
- Phase 2: tools-creator AFTER phase 1 (needs agent files to exist)
- MCP servers preferred over custom tool implementations

---

## Agency Swarm — Sequential Pipeline (Handoff Pattern)

**When:** Need agents to hand off rather than parallel-execute

```python
from agency_swarm.tools.send_message import SendMessageHandoff
agent = Agent(..., send_message_tool_class=SendMessageHandoff)
```

---

## Composio — Tool Discovery Sequence

**When:** Need to use an external integration not covered by specialized tools

1. `ManageConnections` — check what's already connected
2. `SearchTools(query="intent", toolkit="TOOLKIT_NAME")` — discover candidate tools
3. `FindTools(tool_names=["TOOL_NAME"], include_args=True)` — get exact params
4. `ExecuteTool` (simple) or `ProgrammaticToolCalling` (complex/multi-step)

---

## Knowledge Management — Saving an Insight

**When:** Important context, preference, or pattern discovered in a session

```bash
# CLI shortcut:
./scripts/save_insight.sh "CATEGORY" "Title" "Content"
# Categories: PROFILE, PROJECT, RESOURCE, SKILL, LESSON

# Or append directly to today's log:
echo "## [SKILL] Pattern Name" >> knowledge/daily_logs/$(date +%Y-%m-%d).md
echo "Content here..." >> knowledge/daily_logs/$(date +%Y-%m-%d).md
```

---

## Skill Template

```markdown
## Skill Name

**When:** Context for when to apply this

**Steps:**
1. ...

**Lessons:**
- ...
```

