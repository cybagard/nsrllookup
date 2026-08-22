# 05 — Modern dependency stack

Status: open
Type: task
Blocked by: none

Full bump of the 2019–2020-era `api/requirements.txt` and the `python:3.9` base images
(3.9 is EOL): Python 3.12, Flask 3.1, waitress 3.0, pytest (current) + pytest-cov,
coverage + pylint current. Drop `nose`/`nosetests` (abandoned) and `Paste`/`TransLogger`
(`api/app.py:4`) — replace with stdlib logging. Update both Dockerfiles' base image
(`api/Dockerfile:1`, `svr/Dockerfile:1`).

## Comments
