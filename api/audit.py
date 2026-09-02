"""The Audit Trail: a durable, append-only record of every Lookup Session
(ADR-0004).

Because the interface is public, forensic safety comes from auditing rather
than access control. Each Audit Entry is appended as one JSON line to a log
file; appending only ever writes to the end, so the trail is durable and
append-only. The trail is injected into the app so a test can observe the
entries a session produced without reaching into the HTTP internals.
"""

import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


class AuditTrail:
    """An append-only, file-backed Audit Trail."""

    SERVICE_ID = "nsrllookup"

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path
        self._buffer: List[Dict[str, Any]] = []

    def record(self, entry: Dict[str, Any]) -> None:
        """Append one Audit Entry to disk if the trail is file-backed."""
        self._buffer.append(entry)
        if self._path is not None:
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def entries(self) -> List[Dict[str, Any]]:
        """The in-memory entries recorded by this instance this session."""
        return list(self._buffer)

    def read(self) -> List[Dict[str, Any]]:
        """Re-read the entries from disk -- proof the trail is durable."""
        if self._path is None:
            return []
        with open(self._path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
