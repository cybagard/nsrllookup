# coding: UTF-8

"""HTTP layer over the lookup module (Seam 1) + the Audit Trail (ADR-0004).

POST /check names one Algorithm and one or more Digests for a single
Lookup Session, returning one Lookup Result per digest with full
provenance, and records an Audit Entry for the session in the durable,
append-only Audit Trail. /health reports the loaded Release + applied
Delta releases (or not-ready when no Hash Set is provisioned). The
lookup contract and the Lookup Result shape live in
`.scratch/rds-v3-migration/spec.md` -> API contract. POST /check is the
sole lookup contract; the retired MD5-only GET route and nsrllookup socket
client were removed in ticket 13.
"""

import logging
from datetime import datetime
from datetime import timezone

from audit import AuditTrail
from flask import Flask
from flask import jsonify
from flask import request
from waitress import serve

import hasheset
from lookup import look_up

logging.basicConfig(level=logging.INFO)

api = Flask(__name__)

_hash_set = None
_manifest = None
_audit = AuditTrail()


def configure(hash_set, manifest=None):
    """Install the provisioned Hash Set + its manifest the routes answer against."""
    global _hash_set
    global _manifest
    _hash_set = hash_set
    _manifest = manifest


def configure_audit(trail: AuditTrail) -> None:
    """Install the Audit Trail sessions record to (injectable for tests)."""
    global _audit
    _audit = trail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dataset_block():
    return None if _hash_set is None else _hash_set.provenance.dataset()


def _ready() -> bool:
    """The mount is trusted only when its manifest agrees with it."""
    return hasheset.verify_readiness(_manifest, _hash_set)


def _record_session(algorithm, results, results_produced=True):
    """Append the Audit Entry for a finished/attempted session (ADR-0004)."""
    _audit.record({
        "timestamp": _now(),
        "caller": AuditTrail.SERVICE_ID,
        "algorithm": algorithm,
        "results": results if results_produced else None,
        "results_produced": results_produced,
        "dataset": _dataset_block(),
    })


@api.route('/ping')
def ping():
    return jsonify({'result': 'pong'})


@api.route('/check', methods=['POST'])
def check():
    body = request.get_json(silent=True)
    
    if body is None or not isinstance(body, dict):
        _record_session(None, None, results_produced=False)
        return jsonify({'error': 'malformed request body'}), 400
    
    algorithm = body.get('algorithm')
    if algorithm is None or algorithm not in hasheset.SUPPORTED_ALGORITHMS:
        _record_session(algorithm, None, results_produced=False)
        return jsonify({'error': 'unsupported algorithm'}), 400
    
    raw = body.get('hashes')
    if raw is None:
        raw = [body['hash']] if 'hash' in body else []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        _record_session(algorithm, None, results_produced=False)
        return jsonify({'error': 'malformed request body'}), 400
    
    if _hash_set is None:
        return jsonify({'error': 'hash set not provisioned'}), 503
    
    if not _ready():
        _record_session(algorithm, None, results_produced=False)
        return jsonify({'error': 'not ready'}), 503

    set_name = body.get('set')
    if set_name is not None and set_name != _hash_set.provenance.set_name:
        _record_session(algorithm, None, results_produced=False)
        return jsonify({'error': 'unsupported set'}), 400

    results = look_up(_hash_set, raw, algorithm)
    _record_session(algorithm, results, results_produced=True)
    return jsonify({'results': results})


@api.route('/health')
def health():
    if not _ready():
        return jsonify({'ready': False})
    return jsonify({'ready': True, 'dataset': _dataset_block()})


if __name__ == '__main__':
    serve(api,
        host='0.0.0.0',
        port=5000)
