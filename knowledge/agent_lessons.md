# Agent Lessons & Gotchas

## Deployment
- Hostinger deploy must use SSH key auth — password auth was swapped out (commit ed94d1a)
- Deploy target: ~/domains/unklefunk.music/public_html/ (not /public_html/ root)

## Agency Swarm
- Framework version: v1.0.0 (OpenSwarm fork)
- Agent creation is phased: agent-creator + instructions-writer first, THEN tools-creator
- Always confirm PRD with user before starting development
- Collect ALL API keys before any dev work begins

## Session Continuity
- Claude has no access to previous chat histories after session ends
- Knowledge files in knowledge/ are the persistent memory layer
- Tag insights during sessions with [CATEGORY] Title format so consolidation script picks them up

## Scripts
- consolidate_knowledge.py — reads daily_logs/, merges into knowledge files, archives
- save_insight.sh — quick CLI shortcut to log a tagged insight
- setup_cron.sh — installs the 5am cron job (run once)
- render_trend_pdf.py — renders a daily_logs/*.md log to knowledge/daily_logs/pdf/*.pdf (uses reportlab, already in requirements.txt)

## Trend Scout Runs
- Every trend-scout run (the "scout trending sounds" scheduled task) should end with
  `python3 scripts/render_trend_pdf.py knowledge/daily_logs/<date>.md` so the user gets
  a printable/downloadable PDF alongside the markdown log, instead of hunting through
  the PR diff for results.
