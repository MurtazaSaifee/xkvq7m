# Plan

Every design decision agreed before building, plus the build order. Domain terms are defined in [GLOSSARY.md](../GLOSSARY.md); decisions with real trade-offs are in [adr/](adr/); data facts are in [research/elexon-and-market-facts.md](research/elexon-and-market-facts.md).

Guiding rule: **simple, finished completely, under budget** (free tiers only).

## Product

- **Users:** a UK utility's day-ahead purchasing desk.
- **Requirement 1:** show the decision snapshot, the wind outlook as it stood at the decision cutoff.
- **Requirement 2:** quantify forecast accuracy.
- **Data:** national wind only, from Elexon.
  - `FUELHH` filtered to `fuelType=WIND`: actual generation, half-hourly.
  - `WINDFOR`: forecasts, hourly, 8 runs a day.

### Views

1. **Decision view (the main view).** Pick a delivery day and see:
   - the decision snapshot (hourly steps) against actual generation (half-hourly);
   - the walk-forward expected-error band;
   - day KPIs: forecast MWh, actual MWh, and the error.
2. **Accuracy view.** Across all delivery days:
   - MAE, bias, RMSE, P90 absolute error and nMAE;
   - an error histogram;
   - an error-by-horizon curve (1-hour buckets, sample counts on hover, with the current cutoff's horizon range marked);
   - band coverage.
3. **Methodology panel.** A plain-language account of the data, the cutoff rule, alignment, the metrics, why MAPE is skipped, and how the band is built.
4. **Optional, only if time remains:** an hour-of-day × day error heatmap, and a worst-days table linking to the Decision view.

**Shared controls:** a decision cutoff picker with presets (EPEX 09:20, the default; N2EX 09:50; half-hourly auctions 14:30 and 15:30) plus a custom time.

**Out of scope:** auth, accounts, other fuels, demand, prices, alerts.

## Domain rules

- **Delivery days:** 2 Jan to 1 Feb 2026, since the decision days are 1–31 Jan 2026. Times are UTC, which equals UK time in January.
- **Decision forecast:** for each target time, the latest forecast with `publishTime` ≤ the cutoff on the decision day (D-1).
  - At 09:20 this selects the 07:30 run, giving horizons of 16.5–39.5 h.
- **Exclusions:** forecasts with `publishTime` > `startTime` are excluded everywhere, and the excluded count is reported in `/meta`.
- **Alignment:** metrics are computed on the forecast's hourly grid. The actual for hour *h* is the mean of the half-hours starting at *h*:00 and *h*:30.
  - Sensitivity check: also compute the metrics comparing at *h*:00 only, and report the difference in the README.
- **Forecast error:** forecast − actual, in MW. Positive means wind was over-forecast.
- **Expected-error band:** for delivery day D, take the P10/P90 of decision-forecast errors over the 14 delivery days ending two days before D (D-15 … D-2), all known at the decision cutoff (walk-forward, so no lookahead). Report band coverage, with a target of about 80%.
  - Next step, for the video only: condition the band on forecast level.
- **Ingestion window:** WINDFOR publish times from 2025-12-18T00:00Z to 2026-02-01T23:59Z, and FUELHH settlement dates 2025-12-19 to 2026-02-01 inclusive. This covers the band's warm-up (delivery days 19 Dec to 31 Dec, since the band reads up to two days back) and every forecast for target times up to the end of 1 Feb.
- **Missing decision forecasts:** a run published on day P covers 21:00Z P-1 to 21:00Z P+2. A cutoff before 02:30 on the decision day leaves 22:00 and 23:00 of the delivery day without a decision forecast. These are shown as gaps and excluded from the metrics, with the count reported.

## Architecture

- **Ingestion CLI:** httpx fetches the window, validates and deduplicates it, and writes `data/snapshot.duckdb`, which is committed. The API never calls Elexon ([ADR-0001](adr/0001-ingested-snapshot-not-live-proxy.md)).
- **Store:** DuckDB, read-only, accessed only through a repository module. The `ASOF JOIN` implements the decision-forecast rule ([ADR-0003](adr/0003-duckdb-snapshot-store.md)).
- **Backend:** FastAPI + Pydantic v2, uv, DuckDB + numpy, with no pandas to keep the bundle small.
  - Endpoints (typed responses, RFC 7807 errors):
    - `GET /api/v1/health`
    - `GET /api/v1/meta`
    - `GET /api/v1/decision-snapshot?delivery_day=&cutoff=`
    - `GET /api/v1/accuracy?cutoff=`
  - Stdlib JSON logging with a request ID.
- **Frontend:** React + TypeScript + Vite, TanStack Query, ECharts and Tailwind. Types are generated from OpenAPI with `openapi-typescript`. The look is a clean light dashboard.
- **Deployment:** Vercel Hobby (free). The React build is served as static files and FastAPI runs as a Python function with the snapshot bundled in. Docker (`docker compose up`) covers local dev and CI ([ADR-0002](adr/0002-vercel-free-tier-docker-for-dev.md)).

### Repo layout

```
backend/    FastAPI app, ingestion CLI, domain logic, tests (uv)
frontend/   React + Vite + TS app, tests (pnpm)
data/       snapshot.duckdb (committed)
docs/       plan, research, adr, agents
Dockerfile  multi-stage: build frontend → serve with FastAPI
docker-compose.yml, Makefile (dev, test, lint, ingest, gen-types), vercel.json
```

## Engineering practice

- **Tests:**
  - Test-first domain core: selection edge cases (published exactly at the cutoff, nothing before the cutoff, duplicates, alignment), metrics checked against hand-computed fixtures, and band leakage.
  - Ingestion tested on recorded Elexon responses, with no network in CI.
  - API contract tests using httpx `AsyncClient` against a fixture DuckDB.
  - A few Vitest + Testing Library component tests.
  - No end-to-end tests, and no coverage target.
- **CI:** GitHub Actions runs on every PR:
  - ruff, pyright and pytest;
  - eslint, tsc and vitest;
  - `docker build`.

  There are no pre-commit hooks.
- **Workflow:** one ticket (`.scratch/`), one branch, one PR with a self-review description. Commits follow the Conventional Commits format.
- **Repo:** public GitHub, with a random anonymous name. `.scratch/` is gitignored. No company name appears in committed files.

## Build order

| # | Slice | Est. |
|---|---|---|
| 1 | Scaffold repo, uv/pnpm, Docker, Makefile, CI; create the public GitHub repo (ask first) | 1.5 h |
| 2 | Ingestion CLI → `snapshot.duckdb` (recorded-fixture tests) | 2 h |
| 3 | Domain core, test-first: selection, alignment, metrics, walk-forward band | 2.5 h |
| 4 | API endpoints + contract tests + type generation | 1.5 h |
| 5 | Decision view (use the `frontend-design` skill) | 2.5 h |
| 6 | Accuracy view + methodology panel | 2 h |
| 7 | Vercel deploy (GitHub integration: PR previews, `main` deploys to prod) + README | 1.5 h |
| 8 | Video: script, record, upload (unlisted) | 1.5 h |
| — | Buffer, then the optional heatmap and worst-days table | 1 h |

## Deliverables checklist

- [ ] Public GitHub repo with a random name
- [ ] README containing:
  - [ ] a pitch and screenshot
  - [ ] the live link
  - [ ] quick start (`docker compose up`, `make dev`)
  - [ ] a repo map
  - [ ] how it works, including assumptions and the sensitivity check
  - [ ] testing and CI
  - [ ] ADR links
  - [ ] **AI assistance** disclosure: *"Built with Claude Code (Anthropic) as an AI pair programmer for research, scaffolding, code and tests. I directed the design, reviewed every change, and own all decisions (see ADRs)."*
- [ ] Deployed on Vercel. Open every link in incognito mode to check access.
- [ ] Unlisted YouTube video, at most 10 minutes:
  - Part 1: customer pitch, at most 5 minutes.
  - Part 2: tech-lead walkthrough covering architecture, design, analysis, code base and practices, at most 5 minutes.
