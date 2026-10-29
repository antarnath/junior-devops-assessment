# Apex Operations API

A small API that tracks operations work, packaged to run with Docker.

This is my submission for the junior DevOps engineering assessment. It shows a
complete path from **code change → CI checks → container build → deployment →
monitoring → rollback**, with evidence for each step.

---

## Quick start

You need Docker with Compose v2, and Python 3.12+ if you want to run the tests.

```bash
# 1. Create your settings file
cp .env.example .env

# 2. Start everything
docker compose up -d --build

# 3. Check it works
curl http://localhost:8000/healthz
# {"status":"ok","service":"apex-operations-api","version":"0.1.0"}

curl http://localhost:8000/readyz
# {"status":"ready","checks":{"database":"ok"}}
```

Try the API:

```bash
# Create an operation
curl -X POST http://localhost:8000/api/v1/operations \
  -H 'Content-Type: application/json' \
  -d '{"reference":"OPS-1001","title":"Warehouse stock reconciliation","priority":2}'

# List them
curl http://localhost:8000/api/v1/operations
```

Interactive API docs: <http://localhost:8000/docs>

**Stop it:** `docker compose down` · **Stop and delete the data:** `docker compose down -v`

---

## What is in here

```
.
├── app/
│   ├── __init__.py
│   └── main.py              # The whole application in one file
├── tests/
│   ├── conftest.py          # Test setup (in-memory database)
│   ├── test_health.py       # Health and readiness checks
│   ├── test_api.py          # The operations API
│   └── test_failure.py      # A test that fails on purpose
├── .github/workflows/ci.yml # The CI pipeline
├── scripts/
│   ├── deploy.sh            # Build, deploy and check a new version
│   └── rollback.sh          # Go back to the previous version
├── docs/
│   ├── architecture.md      # How it all fits together
│   ├── runbook.md           # What to do when things break
│   ├── decision-memo.md     # My choices and why
│   ├── verification-guide.md# How to check everything works
│   ├── ai-disclosure.md     # Where AI helped
│   └── evidence/            # Proof that it all works
├── Dockerfile               # How the image is built
├── compose.yaml             # The API and the database
├── requirements.txt         # Packages the app needs
├── requirements-dev.txt     # Extra tools for testing and checking
├── pyproject.toml           # Linter and formatter settings
├── pytest.ini               # Test settings
├── .dockerignore
├── .gitignore
├── .env.example
└── README.md
```

---

## Running the tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# The normal tests - all 11 pass
pytest -m "not intentional_failure" -v

# The test that fails on purpose - this is meant to fail
pytest tests/test_failure.py -m intentional_failure -v

# The checks CI runs
ruff check app tests
black --check app tests
mypy app --ignore-missing-imports
```

**What the tests cover:**

| File | Tests | Covers |
|---|---|---|
| `test_health.py` | 4 | Health, readiness, request ID header |
| `test_api.py` | 7 | Create, read, list, duplicate handling, 404, validation, uppercase references |
| `test_failure.py` | 1 | Fails on purpose to prove CI blocks deployment |

---

## The CI pipeline

`.github/workflows/ci.yml` has four jobs. Each one has to pass before the next
can run.

| Job | What it checks | Has to pass? |
|---|---|---|
| `test` | Lint, formatting, types, tests, dependency scan, security scan, secret scan | Yes |
| `prove-deploy-gate` | Runs the failing test and checks it really failed | Yes |
| `build` | Builds the image, scans it for vulnerabilities, checks it runs as non-root | Yes |
| `deploy` | Pushes the image and deploys it | Only runs if all the above passed |

```
test ─────────┬──> build ──┐
              │            ├──> deploy
prove-gate ───┘            │
                           ▼
                (skipped if anything failed)
```

The `deploy` job depends on the `test` and `build` jobs, so if a test fails the
deployment is skipped. That is not just claimed — the `prove-deploy-gate` job
runs the failing test and fails the workflow if it ever stops failing.

### Running the same checks locally

```bash
ruff check app tests && \
black --check app tests && \
mypy app --ignore-missing-imports && \
pytest -m "not intentional_failure" && \
pip-audit -r requirements.txt && \
bandit -r app -ll
```

---

## Deploying and rolling back

```bash
./scripts/deploy.sh 0.1.0     # build, start, wait for health, check the database
./scripts/rollback.sh          # go back to the previous version
./scripts/rollback.sh apex-ops-api:0.1.0   # go back to a specific version
```

Each version gets its own image tag. The scripts remember what is running:

| File | What it holds |
|---|---|
| `.deploy/current-release` | The version running now |
| `.deploy/previous-release` | The one before it — the rollback target |

Both scripts check that the service is healthy before reporting success, so a
failed deploy never looks like a successful one.

---

## Logging and health

**Logs** are one JSON object per line, with a request ID so you can follow a
single request through the logs:

```json
{"method": "GET", "path": "/api/v1/operations", "status": 200, "duration_ms": 4.2, "event": "request.completed", "request_id": "a1b2c3", "level": "info", "timestamp": "2026-10-29T18:33:11.063816Z"}
```

```bash
docker compose logs -f api                          # watch the logs
docker compose logs api | grep '"level":"error"'    # just the errors
```

**Health** is split into two endpoints on purpose:

| Endpoint | Checks | Use it for |
|---|---|---|
| `/healthz` | The process is running | "Should I restart the container?" |
| `/readyz` | The process is running **and** the database is reachable | "Should I send traffic here?" |

If `/healthz` also checked the database, a database outage would put the API
container into a restart loop while the real problem was still there.

**Monitoring proposal** — the rubric asks for a proposal rather than a full
implementation, so I have written it up in
[`docs/decision-memo.md`](docs/decision-memo.md#monitoring-and-alerts-proposal)
with the alerts I would set and why.

---

## Showing a failure working

This is the failure investigation from the review. It removes the database
from under a running API:

```bash
# Stop the database
docker compose stop db

curl -i http://localhost:8000/healthz
# HTTP 200  - the app is still alive, it did not crash

curl -i http://localhost:8000/readyz
# HTTP 503  - but it is not ready to serve traffic
# {"status":"not_ready","checks":{"database":"unavailable"}}

curl -i http://localhost:8000/api/v1/operations
# HTTP 500  - clean error, no internal details leaked
# {"error":"internal_server_error","detail":"An unexpected error occurred.","request_id":"..."}

docker compose logs --tail=20 api    # see what happened

# Fix it
docker compose start db
curl -i http://localhost:8000/readyz
# HTTP 200  - recovered on its own
```

The full procedure is in [`docs/runbook.md`](docs/runbook.md).

---

## Security

| What | How |
|---|---|
| No hard-coded secrets | Every setting comes from an environment variable |
| Nothing secret in git | `.env` is in `.gitignore`; `.env.example` has placeholders only |
| Nothing secret in the image | `.dockerignore` keeps `.env`, keys and certificates out of the build |
| Runs as a normal user | The container runs as `apex` (UID 1001), and CI checks it is not root |
| Small attack surface | No compilers or extra tools in the final image, only what the app needs |
| Dependency scanning | `pip-audit` in CI for known vulnerabilities |
| Image scanning | Trivy scans the built image for known vulnerabilities |
| Code scanning | `bandit` in CI, plus ruff's security rules |
| Pinned versions | Exact versions in `requirements.txt`; builds use `--pull` for a fresh base |
| Database not published | PostgreSQL is only reachable inside the Compose network |

---

## Evidence

Every claim in this README was produced by running the commands in this
repository. The output is saved in [`docs/evidence/`](docs/evidence/README.md).

| Claim | Evidence |
|---|---|
| 11 tests pass | [`docs/evidence/tests.txt`](docs/evidence/tests.txt) |
| The intentional failure really fails | [`docs/evidence/ci-gates.txt`](docs/evidence/ci-gates.txt) |
| Lint, format and types are clean | [`docs/evidence/ci-gates.txt`](docs/evidence/ci-gates.txt) |
| The container runs as non-root | [`docs/evidence/deploy.txt`](docs/evidence/deploy.txt) |
| The stack deploys and serves traffic | [`docs/evidence/deploy.txt`](docs/evidence/deploy.txt) |
| Rollback swaps the running image | [`docs/evidence/rollback.txt`](docs/evidence/rollback.txt) |
| The failure investigation works | [`docs/evidence/incident.txt`](docs/evidence/incident.txt) |

---

## Documentation

| Document | What is in it |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Diagrams, the two health endpoints, how versioning and rollback work |
| [`docs/runbook.md`](docs/runbook.md) | Deploy, rollback, troubleshooting, the failure drill, known limits |
| [`docs/decision-memo.md`](docs/decision-memo.md) | My decisions with reasoning, assumptions, the monitoring proposal, cost estimates, what I'd improve |
| [`docs/verification-guide.md`](docs/verification-guide.md) | **How to check the whole project works** — what happens when you push, and every command to verify it |
| [`docs/ai-disclosure.md`](docs/ai-disclosure.md) | Where AI helped and what I changed |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` fails to build | `docker compose build --no-cache api` |
| `/readyz` returns 503 | The database is unreachable: `docker compose ps`, `docker compose logs db` |
| Tests fail on import | `source .venv/bin/activate` and `pip install -r requirements-dev.txt` |
| `pytest` runs the failing test | Use `pytest -m "not intentional_failure"` |
| Port 8000 is in use | `docker compose down`, then try again |
| Changed `POSTGRES_PASSWORD` and now it will not connect | The volume still has the old password. `docker compose down -v` and start again — this deletes the data |

---

## Notes

Only synthetic data was used. No production systems, no real customer data, no
credentials and no paid cloud resources.
