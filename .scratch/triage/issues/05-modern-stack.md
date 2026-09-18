# 05 — Modern dependency stack

Status: resolved — modern stack (Py3.12/Flask3/waitress3, drop nose/Paste) in `rds-v3-migration/01` (commit `74cf77d`)
Type: task
Blocked by: none

Full bump of the 2019–2020-era `api/requirements.txt` and the `python:3.9` base images
(3.9 is EOL): Python 3.12, Flask 3.1, waitress 3.0, pytest (current) + pytest-cov,
coverage + pylint current. Drop `nose`/`nosetests` (abandoned) and `Paste`/`TransLogger`
(`api/app.py:4`) — replace with stdlib logging. Update both Dockerfiles' base image
(`api/Dockerfile:1`, `svr/Dockerfile:1`).

## Comments
