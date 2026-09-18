# 06 — pytest suite + CI test job

Status: resolved — pytest + CI test job in `rds-v3-migration/02`+`03` (commit `74cf77d`)
Type: task
Blocked by: 05

Migrate the test suite from `nosetests` to pytest + pytest-cov. The compose test commands
(`docker-compose.build.yml:35`, `docker-compose.hub.test.yml:12`) call
`nosetests … --with-coverage --cover-package=.` — rewrite for pytest. Add a CI test job
to `.github/workflows/` (today it holds only codacy/codeql/anchore static scans — no test
job). Update existing tests in `api/tests/unit/` and `api/tests/integration/` for the new
`POST /check` contract (ticket 04). Drop the obsolete top-level `version: "3"` field from
the compose files and pin/`arg` image tags by minor (e.g. `3.12`), not `3.9`.

## Comments
