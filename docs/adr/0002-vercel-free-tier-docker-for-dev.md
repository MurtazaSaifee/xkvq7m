# Deploy on Vercel's free tier; Docker for local dev and CI

The project must run on free tiers, and Heroku has no free tier (Eco is $5/month, Basic $7/month), so we deploy on Vercel's free Hobby plan. The React build is served as static files and FastAPI runs as a Python function with the read-only DuckDB snapshot bundled in. Docker (`docker compose up`) is the local-dev and CI environment, which satisfies the requirement to use Docker. The one exception is if Vercel's new container functions (`Dockerfile.vercel`) work on Hobby within a 30-minute spike, in which case production runs the same image.

## Consequences

- To stay under Vercel's 500 MB bundle and 4.5 MB response limits, the backend avoids heavy dependencies (it uses DuckDB and numpy, not pandas) and returns pre-aggregated data.
- Production has cold starts. The deployed app is a demo, not a latency benchmark.
- A single-container Heroku deploy was the first choice and was rejected only on cost.
