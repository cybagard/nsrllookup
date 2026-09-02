"""Provision/delta-apply smoke checks (build-time, not a seam)."""

import app
import hashlib
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"


def _row(filename, md5, **kw):
    row = {"crc32": None, "md5": md5, "md5sha1": None,
        "sha1": None, "sha256": None, "filename": filename}
    row.update(kw)
    return row


def test_apply_delta_yields_updated_hash_set(tmp_path):
    """Applying a Delta adds rows and rebuilds the index."""
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [
        _row("base.bin", KNOWN_MD5),
        _row("md5only.bin", "11111111111111111111111111111111"),
    ])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1"))
    new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
    updated = hasheset.apply_delta(base_set,
        [_row("delta.bin", new_md5)], "2026.06.1")
    assert updated.is_known("md5", new_md5)
    assert updated.is_known("md5", KNOWN_MD5)
    assert not base_set.is_known("md5", new_md5)


def test_apply_delta_refreshes_provenance(tmp_path):
    """The applied Delta is recorded in the refreshed provenance."""
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1"))
    updated = hasheset.apply_delta(base_set,
        [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
    assert updated.provenance.release == "2026.03.1"
    assert updated.provenance.deltas == ("2026.06.1",)
    assert updated.provenance.dataset() == {
        "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"]}


def test_health_reports_refreshed_provenance(tmp_path):
    """Health reflects the applied Delta after a rebuild."""
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1"))
    updated = hasheset.apply_delta(base_set,
        [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
    app.configure(updated)
    try:
        data = app.api.test_client().get("/health").get_json()
        assert data["dataset"] == {
            "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"]}
    finally:
        app.configure(None)
