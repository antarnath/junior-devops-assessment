# AI Assistance Disclosure

The assessment says AI assistance is allowed but must be disclosed with
specific uses. This is that disclosure.

**Tool used:** Puku CLI, running an Anthropic-hosted model, used interactively
while building this project.

---

## What AI was used for

### 1. Writing the first drafts of the code

| Item | Detail |
|---|---|
| Files | `app/main.py`, `tests/conftest.py`, `tests/test_health.py`, `tests/test_api.py` |
| Why | The 48-hour deadline meant starting from a working draft instead of a blank file |
| How I checked it | Ran the tests (11 passing), ran the linter and formatter, ran the app in Docker and called every endpoint by hand |
| What I changed by hand | Merged several small modules into one `main.py` because the split was unnecessary for a single table. Rewrote the config to use plain environment variables instead of a settings library, and replaced Pydantic schemas with simple validation, because both were over-engineered for this size |

### 2. The Docker and CI files

| Item | Detail |
|---|---|
| Files | `Dockerfile`, `compose.yaml`, `.dockerignore`, `.github/workflows/ci.yml` |
| Why | Getting the CI job dependencies right is fiddly, and a broken Dockerfile wastes a lot of build time |
| How I checked it | Built the image and ran it. Checked the container runs as UID 1001, not root. Started the whole stack and confirmed both containers go healthy |
| What I changed by hand | Removed the Prometheus container and the Trivy scan from the local setup to keep it simple. Added the `prove-deploy-gate` job, which checks the intentional failure test really does fail |

### 3. The deploy and rollback scripts

| Item | Detail |
|---|---|
| Files | `scripts/deploy.sh`, `scripts/rollback.sh` |
| Why | The assessment requires an executable rollback, not just a description of one |
| How I checked it | Ran a full release, a second release, then a rollback, and confirmed the running image changed back |
| What I changed by hand | Rewrote both scripts with plainer wording and simpler comments. Fixed a bug where `die` was called before it was defined |

### 4. The documentation

| Item | Detail |
|---|---|
| Files | `README.md`, `docs/architecture.md`, `docs/runbook.md`, `docs/decision-memo.md`, this file |
| Why | Documentation is a scored deliverable and writing it from scratch takes hours |
| How I checked it | Every instruction in the runbook was followed exactly as written, and the output checked against what the command actually returned |
| What I changed by hand | The reasoning in the decision memo, the assumptions, the trade-offs, and the "what I would improve" section are my own. The AI wrote the scaffolding around them |

---

## What was not AI-generated

- The decision to split liveness from readiness, and the reasoning about why a
  database outage must not cause a restart loop.
- The reasoning about what to cut from my first draft to keep it simple.
- All the trade-off analysis and the cost estimates.
- The interpretation of every test result and log output I looked at.
- All the corrections listed below.

---

## Corrections I made to AI-generated code

| Problem I found | What I changed |
|---|---|
| The first version split the app into `config.py`, `models.py`, `schemas.py`, `database.py` and `logging_config.py` — too many files for one table | Merged everything into `app/main.py` |
| Pydantic schemas added a dependency and complexity for four fields | Replaced with plain dictionary validation in the route handler |
| `create_engine(max_overflow=...)` is not valid for SQLite, which broke every test on import | Made the pool options conditional on the database being PostgreSQL |
| The intentional failure test had a `@pytest.mark.skip`, so it never actually failed and proved nothing | Removed the skip so the test genuinely fails |
| `deploy.sh` called a `die` function before defining it | Moved the function definitions to the top of the script |
| The version was extracted from `__init__.py` with a nested `python3 -c` command that broke shell quoting | Replaced with a simple `sed` command |
| `smoke-test.sh` used a fixed reference, so running it twice returned a 409 error | Made the reference unique per run |
| Ruff flagged the FastAPI `Depends()` pattern and a `datetime` import | Added scoped ignores in `pyproject.toml` and updated the import |
| Black reported formatting drift in several files | Ran `black` and confirmed it was clean |

---

## Verification statement

Every file listed above was executed and the output was checked. The test suite
passes, the intentional failure test fails on purpose, the linter and formatter
are clean, the Docker image builds and runs as a non-root user, the stack
deploys with both containers healthy, and a rollback was performed and
verified.

I can explain and defend every decision in this submission, including the
parts the AI drafted.
