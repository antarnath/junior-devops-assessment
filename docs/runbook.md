# Runbook

What to do when things need deploying, rolling back, or fixing.

All commands are run from the repository root.

---

## 1. Deploy

```bash
# First time only - create your settings file
cp .env.example .env

# Build, start and check the new version
./scripts/deploy.sh 0.1.0
```

`deploy.sh` does this:

1. Checks Docker is installed.
2. Saves the currently running image as the rollback target.
3. Builds the new image.
4. Starts the stack.
5. Waits for the container to report itself healthy.
6. Checks `/readyz` so we know the database is reachable too.

If any step fails the script stops with an error and prints the recent logs.

**Check it worked:**

```bash
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
```

Expected:

```json
{"status":"ok","service":"apex-operations-api","version":"0.1.0"}
{"status":"ready","checks":{"database":"ok"}}
```

**The manual version** (if you prefer not to use the script):

```bash
docker compose build --pull api
docker compose up -d
docker compose ps
```

---

## 2. Roll back

```bash
./scripts/rollback.sh
```

This goes back to the image saved in `.deploy/previous-release`. To pick a
specific image instead:

```bash
./scripts/rollback.sh apex-ops-api:0.1.0
```

The steps are:

1. Find the target image.
2. Restart only the API container with that image (the database is left alone).
3. Wait for it to become healthy.
4. Check `/readyz`.
5. Swap the saved versions around, so the rollback can itself be rolled back.

**Check it worked:**

```bash
docker inspect --format='{{.Config.Image}}' apex-api
```

This should show the older image tag.

**How long should a rollback take?** Under two minutes. If it takes longer,
something else is wrong — go to the incident section below rather than debugging
in place.

---

## 3. When something breaks

### First, check the basics

```bash
docker compose ps                  # is everything running?
docker compose logs --tail=100 api # what do the logs say?
curl -i http://localhost:8000/healthz
curl -i http://localhost:8000/readyz
```

### Read the results

| `/healthz` | `/readyz` | What it means | What to do |
|---|---|---|---|
| 200 | 200 | Everything is fine | Nothing |
| 200 | 503 | The API is up but the database is unreachable | Go to "Database problem" |
| 503 | 503 | The API container itself is not running | Go to "API will not start" |
| 200 | 200 | But requests are failing | Check the logs for the specific error |

### Database problem

```bash
docker compose ps db
docker compose logs --tail=50 db
```

Common causes:
- The database container stopped → `docker compose start db`
- The database ran out of disk → `docker system df`
- The password in `.env` does not match what the database was created with.
  If you changed `POSTGRES_PASSWORD` after the first run, the volume still
  has the old password. Fix it with `docker compose down -v` (this deletes the
  data) and start again.

### API will not start

```bash
docker compose logs api
```

Look for:
- `OperationalError` → the database is not reachable. Check the database first.
- `ModuleNotFoundError` → the image is missing a dependency. Rebuild it:
  `docker compose build --no-cache api`
- The container restarts repeatedly → run it in the foreground to watch:
  `docker compose up api`

### Rebuild from scratch

If nothing makes sense:

```bash
docker compose down -v    # removes the containers AND the data
docker compose build --pull --no-cache api
docker compose up -d
```

**This deletes the database contents.** The data is synthetic test data, so
that is fine here.

---

## 4. Demonstrating a failure (for the assessment)

This is the failure investigation to show in the review. It takes the database
away and shows what happens.

```bash
# Step 1 - stop the database
docker compose stop db

# Step 2 - the app is still alive
curl -i http://localhost:8000/healthz
# HTTP 200

# Step 3 - but it is not ready to serve traffic
curl -i http://localhost:8000/readyz
# HTTP 503
# {"status":"not_ready","checks":{"database":"unavailable"}}

# Step 4 - requests that need the database fail cleanly
curl -i http://localhost:8000/api/v1/operations
# HTTP 500
# {"error":"internal_server_error","detail":"An unexpected error occurred.","request_id":"..."}

# Step 5 - the logs show what happened
docker compose logs --tail=20 api

# Step 6 - fix it
docker compose start db
curl -i http://localhost:8000/readyz
# HTTP 200 - recovered
```

**What this shows:** the app did not crash, it did not start restarting itself,
and the error returned to the caller did not leak any internals. It failed
gracefully and recovered by itself.

The captured output is in `docs/evidence/`.

---

## 5. Routine tasks

| Task | Command |
|---|---|
| Start the stack | `docker compose up -d` |
| Stop the stack | `docker compose down` |
| Stop and delete the data | `docker compose down -v` |
| Rebuild after a code change | `docker compose build api && docker compose up -d` |
| See the logs | `docker compose logs -f api` |
| Check for known dependency vulnerabilities | `pip-audit -r requirements.txt` |
| Check the code for security issues | `bandit -r app -ll` |
| Check the built image for vulnerabilities | See "Image scan fails in CI" below |

---

## 5b. If the image scan fails in CI

The `Build Image` job fails if Trivy finds a HIGH or CRITICAL vulnerability in
the image. Work through it in this order:

1. **Read the Trivy output in the job log.** It names the package, the
   installed version and the version that fixes it.

2. **If it is one of the application's own packages**, fix it by bumping the
   version in `requirements.txt` and pushing. That is the correct fix.

3. **If it is a Debian OS package**, it comes from the base image. Rebuilding
   with `docker compose build --pull api` picks up a newer base image, which
   usually has the fix.

4. **Only if the finding genuinely does not apply** — for example the code is
   vendored inside a tool the application never calls — add it to
   `.trivyignore.yaml` with the reason and a review date:

   ```yaml
   vulnerabilities:
     - id: CVE-2026-97687
       paths:
         - "usr/local/lib/python3.12/site-packages/pip/_vendor/urllib3"
   ```

   Every entry needs a reason. A file of unexplained ignores is worse than no
   ignore file, because it looks like the scan passes when it does not.

5. **Do not lower the severity or turn off the scan** to make it pass. The
   point of the gate is that it fails when there is a real problem.

---

## 6. If you need help

| Situation | Who |
|---|---|
| Not sure if it is the app or the database | Check `/healthz` vs `/readyz` first — that tells you which one it is |
| Deployment failed, need to go back | `./scripts/rollback.sh` |
| Broken and unclear | `docker compose down -v` and start again (data is disposable) |
| Something not covered here | `docs/decision-memo.md` has the reasoning behind each choice |

---

## 7. Known limits

- The database table is created when the app starts, not through a migration
  tool. A real project would use something like Alembic so schema changes are
  versioned.
- There is no login on the API. This is a local test environment only.
- Logs go to the terminal. A real setup would ship them somewhere searchable.
- The rollback script works on this machine only. A real deployment would
  change the image reference on a server or a container service.
