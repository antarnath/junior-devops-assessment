# Verification Guide

How to check this project works, from scratch. Every command below was run and
the output checked.

---

## Part 1: What happens when you push to GitHub

Your repository has a workflow file at `.github/workflows/ci.yml`. GitHub
reads that file and runs it automatically on every push to `main` and on every
pull request.

### What happens, step by step

**1. GitHub sees your push.** It reads `.github/workflows/ci.yml` and starts a
workflow run. It gets a free Linux virtual machine for each job that runs in
parallel.

**2. Four jobs start:**

| Job | What it does | Needs |
|---|---|---|
| `test` | Lint → format → type check → tests → dependency scan → code scan → secret scan | — |
| `prove-deploy-gate` | Runs the deliberately failing test, checks it really failed | `test` |
| `build` | Builds the image, scans it, checks it runs as non-root | `test` |
| `deploy` | Pushes the image and deploys | `test` + `build` |

**3. The gate works like this:**

```
test fails  →  build is SKIPPED  →  deploy is SKIPPED  →  nothing is deployed
```

The `deploy` job has `needs: [test, build]`. GitHub will not start a job whose
dependency failed. This is the mechanism that stops a broken release.

**4. The `deploy` job is also limited to `main`.** It has:

```yaml
if: github.ref == 'refs/heads/main' && github.event_name == 'push'
```

So a push to any other branch runs the checks but never deploys.

**5. What you will see on the Actions page:**

```
Run #2  ✓ Lint, Test & Scan              (success)
        ✓ Prove Deploy is Blocked...     (success)
        ✓ Build Image                    (success)
        ✓ Deploy                         (success)
```

That is the run that is recorded in
[`docs/evidence/ci-run.txt`](evidence/ci-run.txt).

---

## Part 2: Check it on GitHub

Open: <https://github.com/antarnath/junior-devops-assessment/actions>

| What to look at | What it proves |
|---|---|
| The `test` job log | Each check ran and passed, with the 11 test names listed |
| The `prove-deploy-gate` job log | The intentional test failed on purpose, and the job confirmed it |
| The `build` job log | The image built, Trivy found no serious problems, and the container is not root |
| The `deploy` job log | The image was pushed to `ghcr.io` with the commit SHA and `latest` tags |

Click any job to see the full log. The `Run tests` step shows every test name
and its result.

You can also check the published image from your machine:

```bash
docker manifest inspect ghcr.io/antarnath/junior-devops-assessment/apex-ops-api:latest
```

That should print the image manifest, which proves the deploy job really
published something.

---

## Part 2b: What happens when a test fails

This is the part the assessment cares about most, so it is worth demonstrating
live.

1. Open `tests/test_failure.py` and change `418` to `200` on the line with the
   assertion. That makes the "failing" test start passing.
2. Push to any branch and open a pull request.
3. Watch the Actions page. The `test` job fails, and `build`, `deploy` are
   both **skipped**.
4. Put the `418` back and push again. Everything goes green.

To see it on `main` instead of a pull request, push a commit that breaks a
test. The `test` job fails, `build` and `deploy` are skipped, and nothing is
published to `ghcr.io`. You can check that with:

```bash
docker manifest inspect ghcr.io/antarnath/junior-devops-assessment/apex-ops-api:latest
```

The manifest will still be the old one, because the new image was never
pushed.

---

## Part 3: Check it on your machine

This is what you will demo in the review.

### Setup

```bash
cd /media/antar-chandra-nath/Media/Job_placement/Apex-junior-dev-ops

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env
```

### Check 1 — the tests pass

```bash
pytest -m "not intentional_failure" -v
```

Expect **11 passed, 1 deselected**.

### Check 2 — the failing test really fails

```bash
pytest tests/test_failure.py -m intentional_failure -v
```

Expect **1 failed**, with `assert 200 == 418`. This is deliberate — it is the
proof that the CI gate works. Do not "fix" it.

### Check 3 — the linting and security checks pass

```bash
ruff check app tests          # All checks passed!
black --check app tests       # 6 files would be left unchanged
mypy app --ignore-missing-imports   # Success: no issues found
pip-audit -r requirements.txt  # No known vulnerabilities found
bandit -r app -ll             # 0 issues at every severity
```

### Check 4 — the container runs as non-root

```bash
docker build -t apex-ops-api:0.1.0 .
docker run --rm --entrypoint id apex-ops-api:0.1.0
```

Expect `uid=1001(apex) gid=1001(apex) groups=1001(apex)` — not `uid=0(root)`.

### Check 4b — the image has no known vulnerabilities

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 image --ignorefile .trivyignore.yaml \
  --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 apex-ops-api:0.1.0
```

Expect **0 vulnerabilities** and exit code `0`. The `--ignorefile` only covers
the findings listed in `.trivyignore.yaml`, each of which has a written
reason and a review date.

### Check 5 — the stack deploys and serves traffic

```bash
docker compose up -d --build
docker compose ps
```

Expect both containers to show `(healthy)`:

```
NAME       IMAGE                STATUS
apex-api   apex-ops-api:0.1.0   Up (healthy)
apex-db    postgres:16-alpine   Up (healthy)
```

```bash
curl http://localhost:8000/healthz
# {"status":"ok","service":"apex-operations-api","version":"0.1.0"}

curl http://localhost:8000/readyz
# {"status":"ready","checks":{"database":"ok"}}

curl -X POST http://localhost:8000/api/v1/operations \
  -H 'Content-Type: application/json' \
  -d '{"reference":"OPS-1001","title":"Demo","priority":2}'

curl http://localhost:8000/api/v1/operations
```

### Check 6 — release and rollback

```bash
./scripts/deploy.sh 0.1.0     # Deployed apex-ops-api:0.1.0 successfully
./scripts/deploy.sh 0.2.0     # Deployed apex-ops-api:0.2.0 successfully

docker inspect --format='{{.Config.Image}}' apex-api
# apex-ops-api:0.2.0

./scripts/rollback.sh         # Rolled back to apex-ops-api:0.1.0 successfully

docker inspect --format='{{.Config.Image}}' apex-api
# apex-ops-api:0.1.0
```

### Check 7 — the failure investigation

```bash
docker compose stop db

curl -i http://localhost:8000/healthz    # HTTP 200  - still alive
curl -i http://localhost:8000/readyz     # HTTP 503  - not ready
docker compose logs --tail=20 api        # the cause in the logs

docker compose start db
curl -i http://localhost:8000/readyz     # HTTP 200  - recovered by itself
```

### Clean up

```bash
docker compose down -v
```

---

## Part 4: The checklist from the assessment

| The assessment asks for | Where it is | Verified by |
|---|---|---|
| Dockerfile with health check and non-root | `Dockerfile` | Check 4 |
| CI that installs, lints, tests, builds, and blocks on failure | `.github/workflows/ci.yml` | Part 2, Part 2b, Check 1-3 |
| Compose with app, database, config, persistent storage | `compose.yaml` | Check 5 |
| Release and rollback with versioned images | `scripts/deploy.sh`, `scripts/rollback.sh` | Check 6 |
| Structured logs, health checks, metrics proposal | `app/main.py`, `docs/decision-memo.md` | Check 5, Check 7 |
| Secrets, least privilege, scanning, cost | `docs/decision-memo.md` | Check 3, Check 4b |
| 6+ automated checks, one intentionally failing | `tests/` (11 + 1) | Check 1, Check 2 |
| CI evidence, deployment demo, rollback evidence | `docs/evidence/` | Part 2 |
| Runbook for deploy, rollback, incidents | `docs/runbook.md` | Part 3 |
| README with setup steps | `README.md` | Part 3 |
| Architecture diagram | `docs/architecture.md` | — |
| Decision memo | `docs/decision-memo.md` | — |
| AI disclosure | `docs/ai-disclosure.md` | — |
