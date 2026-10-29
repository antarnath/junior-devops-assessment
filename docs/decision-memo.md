# Decision Memo

**Author:** [Your name]
**Date:** [Date]

---

## Summary

I built a small API that tracks operations work, packaged it as a Docker
container, deployed it locally with Docker Compose, and set up a CI pipeline
that stops the deployment if the tests fail.

I kept it simple on purpose. The assessment is about showing good judgement and
that things actually work, not about building a big system. Every choice below
is something I can explain and defend in the review.

---

## Decisions

### 1. FastAPI

**Why:** It gives me validation, automatic API documentation at `/docs`, and
it's quick to write. A plain Flask app would also work but FastAPI is less
code for the same result.

**Trade-off:** It brings a few extra dependencies. I pinned every version and
scan them in CI.

### 2. Everything in one file (`app/main.py`)

**Why:** I started with separate files for config, models and database, but
there is only one table and about four settings. Splitting it up made it
harder to follow for no real benefit. One file is easier to review in 30
minutes, which matters here.

**Trade-off:** If the app grew to several tables I would split it up again.

### 3. SQLite for the tests, PostgreSQL for the deployment

**Why:** The tests need to be fast and must not need anything else running, so
they use an in-memory SQLite database. The deployed stack uses the real
PostgreSQL, so the readiness check is testing the actual setup.

**Trade-off:** They are not identical. The only difference that bit me was
connection pool settings, which SQLite does not accept — I made the pool
options conditional. A better approach would run the tests against PostgreSQL
too, but that needs a database running in CI, which is more setup.

### 4. The deployment gate is proven, not claimed

**Why:** The assessment says claiming something works without evidence is a
serious problem. So instead of saying "the pipeline blocks on failure", the
CI has a job that runs the deliberately failing test and checks that it
actually failed. If it ever stops failing, that job fails too — so the
demonstration cannot quietly break.

**Trade-off:** One CI job always fails by design, which looks odd in the job
list. I gave it a clear name (`Prove Deploy is Blocked on Failure`) to make
the reason obvious.

### 5. Two health endpoints instead of one

**Why:** `/healthz` only checks the process. `/readyz` also checks the
database. If one endpoint did both, a database outage would make Docker
restart the API container over and over while the real problem was untouched.
Splitting them means the API stays up and recovers when the database comes back.

**Trade-off:** You have to remember which one to use. The runbook explains it.

### 6. Versioned images with the running version saved on disk

**Why:** Rollback needs to know exactly what to go back to. Saving the tag in
`.deploy/current-release` means `rollback.sh` is a single command rather than
something I have to remember or look up.

**Trade-off:** That file is local to this machine and is not in git. On a real
server the running version would be tracked by the platform instead. The
rollback script also accepts an explicit image name for that case.

### 7. Secrets come from environment variables

**Why:** The assessment lists hard-coded secrets as a serious problem. All
settings are read from environment variables. `.env` is in `.gitignore`,
`.env.example` has placeholders only, and `.dockerignore` stops `.env` from
ending up inside the image.

**Trade-off:** `.env` is still just a file on my laptop. A real deployment
would use a secret manager — I have noted that in the cloud section.

---

## Assumptions

1. The review machine has Docker with Compose v2 and Python 3.12.
2. The API is for internal use. There is no authentication, which the
   assessment allows for a local environment.
3. The data is small, so one PostgreSQL container with a volume is enough.
4. "Apex Operations API" is a generic operations tracker. The table and the
   fields are my own design.
5. I used only synthetic data. No real customer data, no production systems,
   no paid cloud resources.

---

## Monitoring and alerts proposal

The rubric asks for a proposal, so here is what I would put in place and why.

**What I have now:** structured JSON logs with a request ID on every line, the
two health endpoints, and timings for every request. That is enough to debug a
problem by hand.

**What I would add if there were more time:**

| Alert | Fires when | Why it matters |
|---|---|---|
| API is down | `/healthz` fails for 2 minutes | Nothing is being served at all |
| Too many errors | More than 5% of requests return 5xx for 5 minutes | Users are hitting broken behaviour |
| Slow responses | 95% of requests take more than 500ms | Slows down before it becomes an outage |
| Database unreachable | The readiness check fails | The most common cause of API errors |
| Not enough resources | CPU over 85% for 15 minutes | Time to add capacity |

**What tool:** Prometheus scraping a `/metrics` endpoint, with Grafana for the
dashboard and Alertmanager to send the notifications. The API would expose a
few counters (requests, errors, latency) and a gauge for whether the database
is reachable.

**Why not build it now:** it adds a third container and a fair bit of config.
For an API at this size the logs and health checks are enough to debug
problems, and I would rather have spent the time making the deployment and
rollback solid.

---

## Cost-aware cloud path

Nothing here costs money today — it all runs on a laptop.

If it needed to run for real, this is roughly the order I would work in:

| Step | What | Rough monthly cost |
|---|---|---|
| 1 | One container on a small managed container service, plus the smallest managed PostgreSQL | $25-40 |
| 2 | Two or three copies of the container, managed PostgreSQL with backups | $80-150 |
| 3 | Add autoscaling and a managed Prometheus once there is real traffic | $150+ |

The idea is to start small and only pay for more when something actually needs
it. I would not start with multiple regions, extra monitoring, or a separate
log cluster — for an API this small that is cost without benefit.

The managed database is the important part: running PostgreSQL inside the
container platform yourself means you own backups and upgrades.

---

## What I would improve with more time

1. **A migration tool** so database changes are versioned instead of created
   automatically at startup.
2. **Tests against PostgreSQL** in CI, so the tests match what is deployed.
3. **Login and permissions** on the API.
4. **A `/metrics` endpoint** and a real Prometheus setup, as described above.
5. **More tests** around the error paths and the rollback script itself.
6. **Traces**, so a slow request can be followed through the database as well
   as the logs.

---

## AI assistance disclosure

See `docs/ai-disclosure.md` for the full details.
