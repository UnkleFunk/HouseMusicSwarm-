# Knowledge Management System

This directory is the persistent memory layer for all Claude sessions and HouseMusicSwarm agents.

## How It Works

**During a session** — Claude writes important discoveries to `daily_logs/YYYY-MM-DD.md` using the tagging format below.

**Nightly at 5am** — `scripts/consolidate_knowledge.py` runs, reads all unprocessed logs, merges insights into the structured knowledge files, archives the logs, and commits the result to git.

**Next session** — Claude reads the relevant knowledge files at session start, picking up context without you having to re-explain anything.

## File Map

| File | Contains |
|------|----------|
| `profile.md` | Your background, working style, preferences, goals |
| `projects.md` | Active and recent projects with status and key notes |
| `resources.md` | APIs, tools, services, credentials locations |
| `skills.md` | Repeatable patterns, workflows, techniques |
| `agent_lessons.md` | Swarm-specific agent tricks and lessons |
| `daily_logs/` | Raw session logs (input to consolidation) |
| `archive/` | Processed logs, kept for traceability |

## Tagging Format (for daily logs)

Use these section headers in `daily_logs/YYYY-MM-DD.md` so the consolidation script can categorize entries:

```markdown
## [PROFILE] communication preference
Content about a preference or personal context...

## [PROJECT] Project Name
Status update or important note about a project...

## [RESOURCE] Tool or Service Name
API, endpoint, credentials location, usage note...

## [SKILL] Skill or Pattern Name
Repeatable workflow or technique worth preserving...

## [LESSON] Agent or Component Name
A specific lesson learned about an agent or swarm component...
```

## Manual Insight Capture

To save an insight from the command line during or after a session:

```bash
./scripts/save_insight.sh "SKILL" "DocAgent output path" "Always specify output path in the first message or the agent opens a separate confirm step"
```

## Running Consolidation Manually

```bash
python scripts/consolidate_knowledge.py
# or with a dry run to preview changes:
python scripts/consolidate_knowledge.py --dry-run
```

## Cron Setup

```bash
bash scripts/setup_cron.sh
```

This installs a 5am daily cron job that consolidates logs and commits updates.
