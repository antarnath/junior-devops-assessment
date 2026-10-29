# AI Assistance Disclosure

The assessment says AI assistance is allowed but must be disclosed with
specific uses. This is that disclosure.

**Tool used:** Puku CLI, used interactively while building this project. It
runs on a Claude-hosted model and also routes some requests to other model
providers.

---

## What AI was used for

### 1. Writing the first drafts of the code

| Item | Detail |
|---|---|
| Files | `app/main.py`, `tests/conftest.py`, `tests/test_health.py`, `tests/test_api.py` |
| Why | The 48-hour deadline meant starting from a working draft instead of a blank file |
| How I checked it | Ran the tests (11 passing), ran the linter and formatter, ran the app in Docker and called every endpoint by hand |
| What I changed by hand | Merged several small modules into one `main.py` because the split was unnecessary for a single table. Replaced Pydantic schemas with plain validation, and dropped a settings library, because both were over-engineered for this size |

### 2. The Docker and CI files

| Item | Detail |
|---|---|
| Files | `Dockerfile`, `compose.yaml`, `.dockerignore`, `.github/workflows/ci.yml` |
| Why | Getting the CI job dependencies right is fiddly, and a broken Dockerfile wastes a lot of build time |
| How I checked it | Built the image and ran it. Checked the container runs as UID 1001, not root. Started the whole stack and confirmed both containers go healthy. Ran the pipeline on GitHub and fixed the four failures it turned up |
| What I changed by hand | Removed the Prometheus container and the Trivy scan from the local setup to keep it simple. Added the `prove-deploy-gate` job, which checks the intentional failure test really does fail. Split the dependencies into runtime and development files |

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
| What I changed by hand | The reasoning in the decision memo, the assumptions, the trade-offs, the cost estimates, and the "what I would improve" section are my own. The AI wrote the scaffolding around them |

---

## What was not AI-generated

- The decision to split liveness from readiness, and the reasoning about why a
  database outage must not cause a restart loop.
- The reasoning about what to cut from the first draft to keep it simple.
- All the trade-off analysis and the cost estimates.
- The interpretation of every test result and log output I looked at.
- The decision to drop Kubernetes from the scope — it is not needed for the
  assessment and I do not know it well enough to write about it honestly.
- All the corrections listed below.

---

## Corrections I made to AI-generated code

| Problem I found | What I changed |
|---|---|
| The first version split the app into `config.py`, `models.py`, `schemas.py`, `database.py` and `logging_config.py` — too many files for one table | Merged everything into `app/main.py` |
| The first version included a Kubernetes deployment — out of scope and not something I could defend in the review | Removed it entirely |
| Pydantic schemas added a dependency and complexity for four fields | Replaced with plain dictionary validation in the route handler |
| `create_engine(max_overflow=...)` is not valid for SQLite, which broke every test on import | Made the pool options conditional on the database being PostgreSQL |
| The intentional failure test had a `@pytest.mark.skip`, so it never actually failed and proved nothing | Removed the skip so the test genuinely fails |
| `deploy.sh` called a `die` function before defining it | Moved the function definitions to the top of the script |
| The version was extracted from `__init__.py` with a nested `python3 -c` command that broke shell quoting | Replaced with a simple `sed` command |
| `smoke-test.sh` used a fixed reference, so running it twice returned a 409 error | Made the reference unique per run, then removed the script as unnecessary |
| Ruff flagged the FastAPI `Depends()` pattern and a `datetime` import | Added scoped ignores in `pyproject.toml` and updated the import |
| Black reported formatting drift in several files | Ran `black` and confirmed it was clean |
| `starlette 0.41.3` and `pytest 8.3.4` had published advisories that failed the `pip-audit` gate | Bumped `fastapi` to 0.162.0 and `pytest` to 9.0.3 |
| The CI workflow used `continue-on-error` for the failing test, which hid the real result from both `outcome` and `conclusion` | Captured the exit code inside the step and wrote it to `$GITHUB_OUTPUT`, then checked that value |
| The workflow pinned `trivy-action` to a tag that did not exist | Corrected it to `v0.36.0`, which pins a `setup-trivy` version that resolves |
| Trivy found five HIGH findings that all came from pip's own vendored copies of `msgpack`, `setuptools` and `urllib3` | Removed pip from the final image, which cleared all five without suppressing anything |
| The image was still building with the test and linting tools inside it | Split `requirements.txt` (runtime only) from `requirements-dev.txt` (everything else) |

---

## Verification statement

Every file listed above was executed and the output was checked. The test suite
passes, the intentional failure test fails on purpose, the linter and formatter
are clean, the Docker image builds and runs as a non-root user, the image scan
passes with no HIGH or CRITICAL findings, the stack deploys with both
containers healthy, and a rollback was performed and verified.

I can explain and defend every decision in this submission, including the
parts the AI drafted.
