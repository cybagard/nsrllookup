"""Provision/delta-apply smoke checks (build-time, not a seam).

Fixtures model a Delta as a set of insert rows, rendered to NIST's ordered
`.sql` shape and applied by `executescript`; we assert the index rebuild, the
provenance refresh, and that the base is left untouched.
"""

import app
import hashlib
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"


def _row(file_name, md5, **kw):
    row = {"crc32": None, "md5": md5, "sha1": None, "sha256": None,
            "file_name": file_name, "file_size": 0, "package_id": 0}
    row.update(kw)
    return row


def _apply(base_set, rows, release):
     """Apply a fixture Delta rendered as NIST's ordered `.sql`."""
     delta_sql = hasheset.build_delta_sql(rows)
     return hasheset.apply_delta(base_set, delta_sql, release)


def test_apply_delta_yields_updated_hash_set(tmp_path):
     """Applying a Delta adds rows and rebuilds the index."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [
           _row("base.bin", KNOWN_MD5),
           _row("md5only.bin", "11111111111111111111111111111111"),
       ])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
     updated = _apply(base_set, [_row("delta.bin", new_md5)], "2026.06.1")
     assert updated.is_known("md5", new_md5)
     assert updated.is_known("md5", KNOWN_MD5)
     assert not base_set.is_known("md5", new_md5)


def test_apply_delta_refreshes_provenance(tmp_path):
     """The applied Delta is recorded in the refreshed provenance."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     updated = _apply(base_set, [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
     assert updated.provenance.release == "2026.03.1"
     assert updated.provenance.deltas == ("2026.06.1",)
     assert updated.provenance.dataset() == {
          "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"], "dbhash": "deadbeef"}


def test_apply_delta_leaves_base_untouched(tmp_path):
     """Copy-on-apply leaves the base db's rows unchanged."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
     _apply(base_set, [_row("delta.bin", new_md5)], "2026.06.1")
     assert base_set.is_known("md5", KNOWN_MD5)
     assert not base_set.is_known("md5", new_md5)


def test_delta_refused_on_mismatched_set(tmp_path):
     """A Minimal delta is refused against a base of a different Set."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     delta_sql = hasheset.build_delta_sql([_row("delta.bin", KNOWN_MD5)])
     try:
         hasheset.apply_delta(base_set, delta_sql, "2026.06.1",
                              set_name="legacy")
     except ValueError:
         return
     raise AssertionError("expected cross-set application to be refused")


def test_health_reports_refreshed_provenance(tmp_path):
     """Health reflects the applied Delta after a rebuild."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     updated = _apply(base_set, [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
     app.configure(updated, updated.provenance.dataset())
     try:
          data = app.api.test_client().get("/health").get_json()
          assert data["dataset"] == {
               "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"], "dbhash": "deadbeef"}
     finally:
          app.configure(None)
