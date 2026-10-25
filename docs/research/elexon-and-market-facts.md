# Elexon API and market facts

Researched 2026-10-25 by calling the live APIs and reading primary sources. Scripts and raw responses are in the session scratchpad (`.../scratchpad/fetch_all.sh`, `analyze.py`, `an2.py` to `an4.py`), not in the repo.

Legend: **[VERIFIED]** = observed in live API output or read in the primary source. **[UNVERIFIED]** = could not confirm from a primary source, or only seen via a search summary.

Base URL for everything below: `https://data.elexon.co.uk/bmrs/api/v1`. No API key is needed. The OpenAPI spec is at `https://data.elexon.co.uk/swagger/v1/swagger.json` (the `/bmrs/api/v1/swagger.json` path 404s).

---

## 1. FUELHH (actual generation)

### Endpoint and params [VERIFIED, from swagger and live calls]

`GET /datasets/FUELHH/stream`

| Param | Notes |
|---|---|
| `settlementDateFrom`, `settlementDateTo` | `yyyy-MM-dd`. Both ends inclusive. Cannot be combined with the publish params. |
| `publishDateTimeFrom`, `publishDateTimeTo` | ISO 8601 (`2026-01-01T00:00:00Z`). A bare date also works. Filters on `publishTime`. |
| `settlementPeriod` | array, optional |
| `fuelType` | array, optional. **Server-side filter works** (`fuelType=WIND` returns only WIND). Without it you get 20 fuel types per half-hour (BIOMASS, CCGT, COAL, INTELEC, INTEW, INTFR, INTGRNL, INTIFA2, INTIRL, INTNED, INTNEM, INTNSL, INTVKL, NPSHYD, NUCLEAR, OCGT, OIL, OTHER, PS, WIND). |

Exact URL used for the January window:

```
https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?settlementDateFrom=2025-12-25&settlementDateTo=2026-02-02&fuelType=WIND
```

The stream returns a bare JSON array. The non-stream `/datasets/FUELHH` takes the same filters plus `format=json`, and then wraps the array as `{"data":[...]}`. Its record schema is the same. The swagger text calls the stream variant "optimised JSON payload ... aimed at frequent requests". I did not test whether the non-stream endpoint has a row or date cap (the one call I made, a single day, was fine). [UNVERIFIED for large ranges]

### Sample record [VERIFIED]

```json
{"dataset":"FUELHH","publishTime":"2026-01-03T00:00:00Z","startTime":"2026-01-02T23:30:00Z","settlementDate":"2026-01-02","settlementPeriod":48,"fuelType":"WIND","generation":14202}
```

### Semantics

- **Resolution:** 30 minutes. `startTime` always falls on :00 or :30. [VERIFIED]
- **Units:** `generation` is MW, an average over the 30-minute period. The swagger description says "average MW values over 30 minutes for each category". Values are integers; WIND in Jan 2026 ranges from 1,695 to 17,805 with mean about 10,900. [VERIFIED]
- **Time zone:** `startTime` and `publishTime` are UTC (`Z` suffix). In January, GMT equals UTC, so settlementDate/settlementPeriod line up with UTC: SP1 starts 00:00Z, SP48 starts 23:30Z. [VERIFIED]
- **`publishTime`** is normally `startTime + 30 min` (the end of the period). [VERIFIED: 1,916 of 1,920 records]
- **Counts for Jan 2026 WIND** [VERIFIED]:
  - 31 days × 48 = **1,488 records** with `startTime` in Jan 2026 UTC (identical whether queried by settlementDate or publish time).
  - The query 2025-12-25 to 2026-02-02 (settlementDate) returned 1,920 records = 40 days × 48.
  - A whole-year query (2025-01-01 to 2026-01-31) returned 19,008 records = 396 × 48.
- **Duplicates:** none. Each `startTime` appears once, so the stream returns the current value only. **Revisions are not visible**: the stream gives no history, so I cannot tell whether FUELHH values were revised after first publication. A settlement-date query and a publish-time query returned identical values for all 1,872 overlapping periods. [VERIFIED no dups; revision history UNVERIFIED]
- **Gaps:** none in Dec 25 to Feb 2 (every 30-minute slot present). [VERIFIED]
- **Late-published rows:** 4 of 1,873 records on 2026-01-15 had `publishTime` 12:26Z rather than start+30min (catch-up after a delayed publish; this is the same day the WINDFOR 11:30 run was replaced by one at 12:25). Values were still present. [VERIFIED]

---

## 2. WINDFOR (forecasts)

### Endpoint and params [VERIFIED]

`GET /datasets/WINDFOR/stream` accepts **only** `publishDateTimeFrom` and `publishDateTimeTo`. There is no `startTime` filter and no `fuelType` (national wind only). With no params it returns just the latest publication (73 records). The swagger text: "Specific publish time filters may be supplied, otherwise this will retrieve the latest published forecast."

Exact URL used:

```
https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream?publishDateTimeFrom=2025-12-20T00:00:00Z&publishDateTimeTo=2026-02-02T00:00:00Z
```

The non-stream `/datasets/WINDFOR` takes the same params plus `format=json` and wraps the result as `{"data":[...]}`. Same record schema.

### Sample record [VERIFIED]

```json
{"dataset":"WINDFOR","publishTime":"2026-01-01T22:30:00Z","startTime":"2026-01-01T00:00:00Z","generation":19960}
```

### Resolution, cadence, horizon [all VERIFIED from the live data, Dec 20 2025 to Feb 1 2026]

- **`startTime` resolution is HOURLY** (all 25,696 records have minutes `:00`). This is coarser than FUELHH (30 min), so alignment is needed: one forecast hour T maps to actual half-hours T and T+30min. Whether the hourly value represents the hour mean or a point value is not stated in the API docs. [UNVERIFIED]
- **Publish cadence: 8 runs per day**, at 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30 and 22:30 UTC. Intervals between runs are 2h, 3h or 4h. 352 distinct publishTimes between Dec 20 and Feb 1 = 44 days × 8. Exception: on 2026-01-15 the 11:30 run is missing and a run appears at **12:25** instead (late replacement; has the same 73-row shape). Elexon's glossary page describes an older 4-per-day schedule (04:30, 10:30, 16:30, 22:30, 49 values); the current API data differs from that, so treat the glossary as outdated. [Glossary via search summary, UNVERIFIED]
- **Each run contains exactly 73 hourly rows** (352 runs × 73 = 25,696). The window is fixed in absolute time: it starts at **21:00Z on the day before the publish date** and runs 72 hours to 21:00Z on publish date + 2. Example: any run on 2026-01-15 covers 2026-01-14T21:00Z to 2026-01-17T21:00Z.
- **Horizon = startTime − publishTime**, over all rows: min **−25.5 h**, max **+66.5 h**. Because the window start is fixed, the early part of every run is already in the past.
  - 5,281 of 25,696 rows (about 20.5%) have `startTime < publishTime` (negative horizon). For those rows the value is frozen: for the 962 targets I checked with at least 2 post-target runs, all post-target values were identical across runs. They differ from the last pre-target forecast in most cases (equal in only 84 of 1,052), and they are not close to the FUELHH actuals, so they are not an "actual". What they are is not documented. [UNVERIFIED meaning]. **Filter these out with `publishTime <= startTime`** before any accuracy analysis (or you'd be scoring frozen leftovers).
  - Non-negative horizons span 0.5 h to 66.5 h.
  - Per target hour (Jan), the longest-lead forecast is 43.5 to 66.5 h (median 55 h) ahead.
- **Forecasts per target `startTime`:** between 8 and 32 rows, mostly 24 (968 target hours have 24, 48 have 16, 48 have 8, 41 have 32; edge targets at the ends of the queried range have fewer). Of these, only the runs with `publishTime <= startTime` are real forecasts (roughly 14 to 18 per hour).
- **No duplicate (publishTime, startTime) pairs. No missing hours** (every hourly `startTime` from 2025-12-19T21:00Z to 2026-02-03T21:00Z is present). `generation` is an integer MW with no nulls; observed range 1,981 to 21,353. Units are not stated in the swagger. MW is inferred from the magnitude matching FUELHH. [UNVERIFIED units]
- **Record counts** (query above, publishTime Dec 20 2025 to Feb 1 2026, 25,696 rows total):
  - `startTime` in Jan 2026 (UTC): **18,104 rows** across 744 distinct hours.
  - Rows with `startTime` in 2026-01-02..2026-02-01 (delivery days for January decisions): 18,080.
  - Of those, rows with `publishTime <= startTime` (usable forecasts): 14,383.
  - Rows with `publishTime` within Dec 31 to Jan 31: 18,688.
- **Which delivery days need which runs:** a run published on D-1 covers all 24 UTC hours of delivery day D, because the window reaches back to 21:00Z two days earlier and forward to 21:00Z two days later. For purchases in January 2026, delivery days are 2 Jan to 1 Feb, so publishTimes are needed from 2025-12-31 to 2026-01-31. Fetching from 2025-12-20 gives margin. Every D-1 07:30 run exists for D = Jan 2 to Feb 1. [VERIFIED]

### What the "latest forecast available at decision time" looks like [VERIFIED on Jan 15 delivery day]

- Cutoff 09:20 on D-1 selects the **07:30 run**, whose horizons for delivery-day hours range from 16.5 h (00:00Z) to 39.5 h (23:00Z).
- Cutoff 09:30 or later (e.g. 09:50 N2EX closure) selects the **09:30 run**.

---

## 3. Request limits and timings

All tests run 2026-10-25 from a Mac on home network, single request each, no auth. [VERIFIED]

| Request | HTTP | Size | Time | Rows |
|---|---|---|---|---|
| FUELHH WIND, settlementDate 2025-12-25 to 2026-02-02 | 200 | 348 KB | 1.5 s | 1,920 |
| FUELHH WIND, publish 2025-12-25 to 2026-02-02 | 200 | 340 KB | 1.5 s | 1,873 |
| FUELHH WIND, settlementDate 2025-01-01 to 2026-01-31 (13 months) | 200 | 3.4 MB | 2.3 s | 19,008 |
| FUELHH all fuel types, 1 day | 200 | 174 KB | 1.6 s | 960 |
| WINDFOR, publish 2025-12-20 to 2026-02-02 | 200 | 2.9 MB | 2.4 s | 25,696 |
| WINDFOR, publish 2025-10-01 to 2026-02-02 | 200 | 8.2 MB | 2.6 s | 72,440 |
| WINDFOR, publish 2025-01-01 to 2026-02-02 (13 months) | 200 | 26 MB | 4.1 s | 231,702 |

- **No maximum date range was hit** on the stream endpoints, up to 13 months. This matches the developer portal: "no restrictions or limits on data return" for stream endpoints (https://developer.data.elexon.co.uk/, read via WebFetch). Responses come back as a single uncompressed JSON array (no pagination).
- **Rate limit:** a search summary of the official guidance page (https://bmrs.elexon.co.uk/api-documentation/guidance) says **5,000 requests/minute/user**, with HTTP 429 beyond that and possible extra endpoint-specific limits. I could not read that page directly (it is a JS single-page app), so **[UNVERIFIED]**. We need about 2 requests in total, so it is irrelevant for our use. I did not trigger any 429.
- **Practical implication:** the whole January dataset is under 4 MB and about 4 s to fetch. The app can fetch once at start-up (or bake a snapshot into the image) and compute in memory. A fallback snapshot file is cheap insurance against API downtime during the demo.
- `HEAD` requests return 404 on these endpoints; use GET.

---

## 4. GB day-ahead market timing

### Gate closures

| Auction | Operator | Gate closure (UK time) | Results | Source |
|---|---|---|---|---|
| GB (hourly) Day-Ahead | EPEX SPOT | **09:20** | from 09:30 | EPEX Trading Brochure Dec 2024; EPEX press release 3 Dec 2020 |
| GB 30-min Day-Ahead | EPEX SPOT | **15:30** | from 15:45 | EPEX Trading Brochure Dec 2024 |
| N2EX GB (hourly) Day-Ahead | Nord Pool | **09:50** | by 10:00 | Nord Pool GB Product Specifications (effective 18 Apr 2023); Nord Pool support article (modified 26 Jul 2022) |
| GB Half-hourly | Nord Pool | **14:30** | not stated in the spec | Nord Pool GB Product Specifications (effective 18 Apr 2023), section 4.1 |

Quotes and notes:

- EPEX press release (3 Dec 2020): the GB Day-Ahead auction moved "from currently 11:00 GMT to 9:20 GMT, with results being available at 9:30 GMT", effective 1 January 2021, after GB left Single Day-Ahead Coupling. https://www.epexspot.com/en/news/exchange-council-welcomes-new-timing-gb-day-ahead-auction (fetched with curl and a browser User-Agent; WebFetch gets 403).
- EPEX Trading Brochure, Dec 2024 (`https://epexspot.com/sites/default/files/2024-12/_Trading%20brochure%202024%20December%20%281%29.pdf`, read locally): "GB 60 min Day-Ahead auction timing has been moved up from 11:00 GMT to 9:20 GMT" and "GB 30 min Day-Ahead auction at 15:30 GMT". "An auction takes place once a day, 365 days a year. Results are published as soon as possible from 9:30 GMT and 15:45 GMT respectively."
- Nord Pool product spec (`https://www.nordpoolgroup.com/497dea/globalassets/download-center/rules-and-regulations/product-specifications-gb-18.04.23.pdf`): GB Auction "Gate Closure: 09:50 GMT/BST"; Half-Hourly Auction "Gate Closure: 14:30 GMT/BST".
- Nord Pool support article "About the N2EX Day Ahead Auction": "Gate closure time is 09:50 GMT / 10:50 CET and results are published at latest 10:00 GMT / 11:00 CET." https://support.nordpoolgroup.com/support/solutions/articles/8000088463-about-the-n2ex-day-ahead-auction
- Nord Pool GB Day-ahead Market Regulations (effective 30 Sep 2021) defer to the product specs for gate closure. They say a delay triggers operational messages "no later than 10:00 UK time" and that the auction fails if not run "before 22:00 UK time on the day prior to the Delivery Day". https://www.nordpoolgroup.com/4a83cb/globalassets/download-center/rules-and-regulations/21_09_30_gb-day-ahead-market-regulations.pdf
- **Dated caveat:** I found no 2025 or 2026-dated edition of the EPEX brochure or Nord Pool spec. The newest sources are Dec 2024 (EPEX) and Apr 2023 (Nord Pool). A web search summary also mentioned an EPEX page showing 10:20 CET/CEST for the GB auction, which equals 09:20 UK time. I treat the times as unchanged for Jan 2026 but could not confirm against a 2026 document. [UNVERIFIED for 2026]
- EPEX writes "GMT" while Nord Pool writes "GMT/BST". Read literally, EPEX's "GMT" could mean fixed UTC (09:20 UTC = 10:20 BST in summer), but its news item uses "9:20 GMT" and a search summary indicated a CET-referenced time that implies UK local. This only matters in summer; it is irrelevant for January. [ambiguity UNVERIFIED]
- **Which to use as the default decision cutoff:** the main hourly day-ahead auction is where a day-ahead purchase decision lands. **09:20 UK time on D-1 (EPEX) is the earliest and most conservative cutoff; 09:50 (N2EX) is the later one.** In terms of WINDFOR runs, 09:20 picks the 07:30 run and 09:50 picks the 09:30 run. The half-hourly auctions (14:30 Nord Pool, 15:30 EPEX) would pick the 11:30 and 15:30 runs respectively. Make the cutoff a parameter with a default of 09:20 and document why.

### Time zone

- In January the UK is on GMT, which equals UTC. There is no BST in January, so UK local time equals UTC for the whole of Jan 2026 and the 09:20 cutoff equals 09:20Z. [VERIFIED by gov.uk]
- **BST 2026:** clocks go forward at 01:00 on the last Sunday in March: **Sunday 29 March 2026**. Clocks go back on **Sunday 25 October 2026** (today). Source: https://www.gov.uk/when-do-the-clocks-change (last updated 24 Nov 2025). So Dec 2025 to Feb 2026 is all GMT.

---

## 5. Deployment facts

### Heroku

- **No free tier.** Free dynos, hobby-dev Postgres and free Redis ended on 28 Nov 2022 (Heroku changelog: https://devcenter.heroku.com/changelog-items/2502, read via search summary; the dyno-types page does not mention free dynos). [Changelog page itself UNVERIFIED by direct fetch; pricing page consistent]
- **Cheapest option:** **Eco, $5/month flat**, covering a pool of 1,000 dyno hours shared across all Eco dynos in the account. 0.5 GB RAM, sleeps after 30 minutes of no traffic, personal accounts only. **Basic is $7/month**, always on, 0.5 GB. Source: https://www.heroku.com/pricing and https://devcenter.heroku.com/articles/dyno-types (both read via WebFetch).
- **Docker:** The pricing page lists "Deploy with Git and Docker" for Eco and Basic. Deploy via the container stack with a `heroku.yml`: `build: docker: web: Dockerfile`, then `heroku stack:set container` and `git push heroku main`. Limits noted in the doc: no layer caching, build context is the Dockerfile's directory, Cedar-generation apps only. Source: https://devcenter.heroku.com/articles/build-docker-images-heroku-yml. Heroku also supports pushing a prebuilt image to its container registry (not re-read this session).
- The docs did not state the `$PORT` requirement on that page. The Heroku Container Registry and Runtime article covers it (web processes must listen on `$PORT`); I did not re-read it. [UNVERIFIED this session]
- Billing needs a card on file, so Heroku cannot be free. It costs about $5 for a short demo window.

### Vercel

- **Docker containers: yes, now supported** (a change from the older serverless-only picture). Vercel's guide says you can deploy an OCI image as an autoscaling Vercel Function on Fluid compute: put a `Dockerfile.vercel` (or `Containerfile.vercel`) at the project root and Vercel builds it, stores it in Vercel Container Registry, and serves it. Containers listen on port 80 by default (override with `PORT`). Idle functions scale down after 5 minutes in production; SIGTERM with a 30 s grace period. Secure Compute and Static IPs are not supported for container images. Source: https://vercel.com/kb/guide/docker. The page does not state GA or beta status, plan availability, or image size limits. [UNVERIFIED: status, plan, image size limits]
- **Native Python (no Docker):** supported as Vercel Functions, ASGI/WSGI frameworks including FastAPI and Flask, Python 3.12 (default), 3.13, 3.14. Entrypoint `app.py`, `main.py`, `index.py` etc. defining `app`. Source: https://vercel.com/docs/functions/runtimes/python (last updated 2026-08-12).
- **Limits (Fluid compute)**, source https://vercel.com/docs/functions/limitations (last updated 2026-08-24):
  - Max duration: Hobby 300 s (default and max). Pro/Enterprise default 300 s, max 800 s, 1,800 s in beta.
  - Memory: Hobby 2 GB / 1 vCPU; Pro/Enterprise up to 4 GB / 2 vCPU.
  - Bundle size, uncompressed: 250 MB generally, **500 MB for Python**, up to 5 GB with Large Functions (beta).
  - Request or response body: 4.5 MB max, so a response must stay under 4.5 MB (our data is small; a 31-day JSON summary fits easily, but returning the raw 2.9 MB WINDFOR set would be close).
  - pandas plus numpy fits comfortably in 500 MB (typically around 100 to 150 MB installed; not measured here). [size UNVERIFIED]
- Serverless functions are stateless, so in-memory caching is per-instance and cold starts matter; a fixed data snapshot shipped with the function avoids calling Elexon at runtime.
- The requirement "Please use docker" and "deploy in vercel or heroku" is therefore satisfiable either way: Heroku container stack is the established path; Vercel Docker support is new (Dockerfile.vercel) and I have not tested it.

---

## Key take-aways for the build

1. WINDFOR is hourly, FUELHH is half-hourly. Align by mapping each hourly forecast to both half-hours (or averaging actuals to the hour) and state the choice.
2. WINDFOR runs 8 times a day. Each run is a 73-hour window from 21:00Z the previous day. Roughly 20% of rows are in the past relative to their publishTime and frozen; drop rows with `publishTime > startTime`.
3. For a 09:20 UK cutoff on D-1 the selected run is 07:30 (horizon 16.5 to 39.5 h for delivery day D); for a 09:50 cutoff it is 09:30. Make the cutoff configurable.
4. Data volume is tiny (about 3 MB), no auth, no range limit hit, about 2 to 3 s per fetch. Fetch once, cache, ship a fallback snapshot.
5. January is wholly GMT = UTC. BST starts 29 Mar 2026.
