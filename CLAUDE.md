# CLAUDE.md

## How to work (general)
- Be brief. Plain, beginner-friendly language. No long summaries.
- Read only what the task needs; use `rg`/`head` instead of reading whole large files. Don't re-read a file already in context.
- Batch independent tool calls. Prefer an existing skill over re-figuring a workflow.
- Smallest change that fully works; no unrequested features or dependencies.
- Ask before installing packages, changing config, or touching company systems. Never print credentials.
- Don't claim something works until verified.

## Browser work
- Claude in Chrome only works from a session on the user's own computer (Desktop app or `claude remote-control`). Cloud sessions cannot reach it.
- Repeated browser workflows (MRI PMX, AvidXchange, Luxer One) belong in skills, not re-explained each time.

## This repo
- Holds Claude Code config: `.claude/settings.json` (ponytail plugin + status line).
- Add project facts below as the repo grows. Keep this file under ~40 lines.
