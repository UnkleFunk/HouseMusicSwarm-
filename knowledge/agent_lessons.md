# Agent Lessons

*Specific lessons about agents and swarm components. Updated by nightly consolidation.*

---

## Virtual Assistant

- Ask about output path preference during onboarding — include it in the initial questions block, never as a separate follow-up
- Email workflow: always create draft first, share preview link, then await approval before sending
- Pre-authorized sends: "send now", "book it", "delete now" skip confirmation
- Remember: capture preferences once, never ask again (see `profile.md`)

## Deep Research Agent

- Best for: market analysis, competitor research, literature reviews, background investigation
- Has ScholarSearch access for academic sources
- Handoff trigger: any "comprehensive research" request from Virtual Assistant

## Data Analyst Agent

- Best for: KPIs, charts, dashboards, revenue analysis, business intelligence
- Handoff trigger: any data/metrics request from Virtual Assistant

## Docs Agent

- Specify output path in first message — agent will ask if not provided, creating an extra round trip
- Handles: PDF, DOCX, Markdown, TXT conversion and creation

## Slides Agent

- `.pptx` export — always confirm output path upfront
- Has a SKILL.md at `slides_agent/pptx/SKILL.md` with specific patterns

## Image/Video Agents

- Generation agents — confirm output directory before triggering long generation jobs

## Orchestrator

- Entry point for all user requests — never executes tasks itself, only routes
- Communication topology: every agent can transfer to any other directly

## General Swarm Notes

- Heartbeats are active in `helpers.py` to prevent tool timeout on long operations
- Context window discipline: log only what you need to see; context is a shared resource
- All agents share `shared_instructions.md` — changes there affect every agent
- `1-3-1 technique` when stuck: define problem + 3 solutions + recommendation

---

## Lesson Template

```markdown
## Agent Name

- Lesson learned...
- Pattern to remember...
```

