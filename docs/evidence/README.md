# Evidence

Output from running the commands in this repository. Every claim in the README
points back to one of these files.

| File | What it shows |
|---|---|
| `ci-run.txt` | The hosted GitHub Actions run: all four jobs green, and the image pulled from `ghcr.io` afterwards. |
| `ci-gates.txt` | Lint, format and type checks all pass. The 11 tests pass. The intentional failure test genuinely fails, with the assertion error. |
| `tests.txt` | Each of the 11 tests listed with its result, plus a coverage report (83%). |
| `deploy.txt` | The container runs as a non-root user (`uid=1001(apex)`). The stack is up with both containers healthy. Both health endpoints respond. An operation is created and listed. A structured JSON log line. |
| `rollback.txt` | Two versioned releases, then a rollback that swaps the running image back and re-checks health. |
| `incident.txt` | The failure investigation: database stopped, liveness stays 200, readiness turns 503, the API returns a clean error, the logs show the cause, and the service recovers on its own. |

## Reproducing it

```bash
# Set up
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# CI gates
ruff check app tests
black --check app tests
mypy app --ignore-missing-imports
pytest -m "not intentional_failure" -v
pytest tests/test_failure.py -m intentional_failure -v   # fails on purpose

# Deploy
docker compose build --pull api
docker compose up -d
docker run --rm --entrypoint id apex-ops-api:0.1.0        # uid=1001(apex)
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/readyz

# Rollback
./scripts/deploy.sh 0.1.0
./scripts/deploy.sh 0.2.0
docker inspect --format='{{.Config.Image}}' apex-api        # 0.2.0
./scripts/rollback.sh
docker inspect --format='{{.Config.Image}}' apex-api        # 0.1.0

# Failure investigation
docker compose stop db
curl -i http://localhost:8000/healthz                      # 200
curl -i http://localhost:8000/readyz                       # 503
docker compose start db
curl -i http://localhost:8000/readyz                       # 200
```

## Still to capture

- **Screenshot of the GitHub Actions run** — the run itself is recorded in
  `ci-run.txt` with the job results pulled from the API. A screenshot of the
  green run in the browser would be a nice addition to the submission.
