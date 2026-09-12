"""Container boot: load the provisioned volume, then serve (Seam 1 entry).

This is the one place the running service turns a mounted, verified data
directory into a ready app. The Provisioner (provision.py) writes the
queryable Hash Set, its Sidecar index, and the Provisioning manifest into the
writable data dir as a one-time, out-of-band step; at boot the service reads
those two artifacts and installs them, so /health reports ready iff the
Provisioning manifest agrees with the mounted Hash Set (ADR-0005) and each
Lookup Result carries the final dbhash (ticket 06).

The service trusts the verified mount (ADR-0006): it does not recompute
dbhash, it reads the token the Provisioner already recorded. No real
Hash Set and no live server are needed to exercise this; the fixture in
test_deploy_smoke provisions the volume with build_minimal_fixture_db and
drives the same entry through Flask's test client.
"""

import os

import app
import hasheset
from audit import AuditTrail
from provision import read_manifest

DATA_DIR = os.environ.get("RDS_DATA_DIR", "/data")
AUDIT_DIR = os.environ.get("RDS_AUDIT_DIR", "/var/log/nsrllookup")

_DB_NAME = "rds.db"
MANIFEST_NAME = "manifest.json"
AUDIT_NAME = "audit.log"


def bootstrap(data_dir=None, audit_dir=None):
    """Read the provisioned Hash Set + manifest and install them in the app.

    The data dir carries the provisioned rds.db and its Provisioning
    manifest; the audit dir carries the append-only Audit Trail. A missing
    db or manifest leaves the app unconfigured, so /health reports
    not-ready and /check refuses to serve -- an unverified volume answers
    nothing (ADR-0005).
    """
    data_dir = data_dir or DATA_DIR
    audit_dir = audit_dir or AUDIT_DIR
    manifest = None
    manifest_path = os.path.join(data_dir, MANIFEST_NAME)
    if os.path.exists(manifest_path):
        manifest = read_manifest(manifest_path)
    db_path = os.path.join(data_dir, _DB_NAME)
    if os.path.exists(db_path):
        record = manifest or {}
        hash_set = hasheset.provision(
            db_path,
            hasheset.Provenance(
                record.get("set"),
                record.get("release"),
                record.get("deltas") or (),
                record.get("dbhash"),
            ),
        )
    else:
        hash_set = None
    app.configure(hash_set, manifest)
    app.configure_audit(AuditTrail(os.path.join(audit_dir, AUDIT_NAME)))
    return hash_set, manifest
