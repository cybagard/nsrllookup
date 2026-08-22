# 10: Apply a Delta release at ingest

**What to build:** the new "stay current" mechanism. Provisioning applies a **Delta release**
onto the current full **Release**, producing an updated **Hash Set**. NIST publishes a full
**Release** quarterly in March and **Delta releases** in June/September/December; this is
the step that layers a **Delta** on without a full re-provision.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** ready-for-agent

- [ ] A **Delta release** is applied onto the current full **Release**, yielding an updated
      current dataset.
- [ ] Provisioning identifies the current **Release** and the **Delta release(s)** applied,
      and records that provenance for the **Hash Set**.
- [ ] Provisioning is a one-time mount/ingest step, not a build or CI step.
- [ ] A smoke check confirms applying a (small sample) **Delta** to a minimal-style DB yields
      a valid updated **Hash Set**.

## Comments
