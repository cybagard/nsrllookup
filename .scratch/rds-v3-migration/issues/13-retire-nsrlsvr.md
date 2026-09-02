# 13: Retire `nsrlsvr`, old `GET /check`, two-service compose/README

**What to build:** remove every retired component. The `nsrlsvr` server, its socket
protocol (the old client), the old one-`GET`/`hash` endpoint and its
`{result: "true|false|invalid hash format"}` response shape, and the two-service compose/
README flow are removed. Only the single-service + mounted-volume model remains. Per
ADR-0001/ADR-0002 the old response shape is a deliberate, breaking change.

**Blocked by:** 11 (Rebuild index + refresh `/health` provenance after a Delta)

**Status:** resolved

- [x] The `nsrlsvr` server and its socket protocol are removed; nothing talks the old
       protocol.
- [x] The old one-digest `GET` endpoint and its response shape are gone; `POST /check` with
        full-provenance **Lookup Results** is the only lookup contract.
- [x] The compose files and README describe the single-service + mounted-volume model, not
         the two-service "prepare the environment / run svr then api" flow.
- [x] No reference to the retired server, its build inputs, or the old response shape
        remains.

## Comments

Removed `svr/` (Dockerfile, docker-entrypoint.sh, prepare-hash-set.sh), `api/nsrllookup.py`
(the socket client), the legacy `GET /check/<hash>` route + its `{result: ...}` response,
the `live`-gated legacy integration test, and the `docker-compose-wait`/`WAIT_HOSTS`
wiring in `api/Dockerfile`. Compose files rewritten as a single-service + read-only mounted
Hash Set + read-write audit trail (no `svr`/`svr-prepare`), and the README rewritten for
`POST /check` + `/health` + the public/audited model. Spec/ADR/ticket docs still mention
`nsrlsvr` as historical context, which is correct.
