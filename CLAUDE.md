# CLAUDE.md

A web app that helps a UK day-ahead power purchasing desk see the national wind forecast available at decision time and measure how accurate those forecasts are. Frontend: React. Backend: Python. Docker for dev and CI; deployed on Vercel.

- `docs/plan.md` holds every agreed design decision and the build order. Read it before planning any work.
- Verified facts about the Elexon APIs, day-ahead auction times and hosting limits are in `docs/research/elexon-and-market-facts.md`.
- Domain language is in `GLOSSARY.md`. Decisions are in `docs/adr/`.

## Constraints

- **Free tiers only** (hosting, CI, databases, monitoring). Flag anything that could cost money before using it.
- **Keep it simple and fast to finish completely.** A small, fully working, well-tested app beats a large, half-finished one. Choose the simpler option unless the extra complexity clearly pays off in the demo or review.
- Commits carry the repo owner's name only: no `Co-Authored-By` or other attribution trailers, in commits or PR descriptions.
- The repo is public and its name is anonymous. Never put a company name in committed files.

## Agent skills

### Issue tracker

Issues are local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels, unchanged (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
