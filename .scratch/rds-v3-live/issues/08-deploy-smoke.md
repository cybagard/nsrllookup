# 08: Fixture deploy smoke (end-to-end)

**What to build:** the demoable terminal slice — a fixture-based **deploy smoke** that proves
the deploy path this session without a multi-gigabyte download: **build the image → run it
→ `/health` reports `ready` and `/check` returns a `known`** against a fixture **Hash Set**,
with `dbhash` in the `dataset` block. A full ~18 GiB real deployment stays an operator step,
out of this ticket.

**Blocked by:** 06 (manifest/readiness + per-result `dbhash`) — the smoke asserts `ready` +
a `known` answer carrying `dbhash`, which exist only after 06.

**Status:** ready-for-agent

- [ ] Build → run the image → `/health` reports `ready` and `/check` returns a `known`
        (with `dbhash` in the `dataset` block), on a fixture **Hash Set**.
- [ ] The smoke stays green on fixtures with **no live server and no real-data download**
        (a real **Hash Set** is not required to run it).
