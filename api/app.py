# coding: UTF-8

"""HTTP layer over the lookup module (Seam 1).

``POST /check`` names one **Algorithm** and one or more **Digests** for a single
**Lookup Session**, returning one **Lookup Result** per digest with full
**provenance**. ``/health`` reports the loaded **Release** + applied **Delta
releases** (or not-ready when no **Hash Set** is provisioned). The lookup
contract and the **Lookup Result** shape live in
``.scratch/rds-v3-migration/spec.md`` -> API contract.

The retired MD5-only ``GET /check/<hash>`` socket route and ``nsrllookup``
client are kept until ticket 13; the new ``POST /check`` is the contract going
forward. The ``NSRLLookup`` import stays on-demand so ``from app import api``
remains boot-safe without a live server.
"""

import logging
import re

from flask import Flask
from flask import jsonify
from flask import request
from waitress import serve

import hasheset
from lookup import look_up

logging.basicConfig(level=logging.INFO)

api = Flask(__name__)

_hash_set = None


def configure(hash_set):
    """Install the provisioned **Hash Set** the routes answer against."""
    global _hash_set
    _hash_set = hash_set


def _dataset_block():
    return None if _hash_set is None else _hash_set.provenance.dataset()


@api.route('/ping')
def ping():
    return jsonify({'result': 'pong'})


@api.route('/check', methods=['POST'])
def check():
    body = request.get_json(silent=True)

    if body is None or not isinstance(body, dict):
        return jsonify({'error': 'malformed request body'}), 400

    algorithm = body.get('algorithm')
    if algorithm is None or algorithm not in hasheset.SUPPORTED_ALGORITHMS:
        return jsonify({'error': 'unsupported algorithm'}), 400

    raw = body.get('hashes')
    if raw is None:
        raw = [body['hash']] if 'hash' in body else []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return jsonify({'error': 'malformed request body'}), 400

    if _hash_set is None:
        return jsonify({'error': 'hash set not provisioned'}), 503

    set_name = body.get('set')
    if set_name is not None and set_name != _hash_set.provenance.set_name:
        return jsonify({'error': 'unsupported set'}), 400

    results = look_up(_hash_set, raw, algorithm)
    return jsonify({'results': results})


@api.route('/health')
def health():
    if _hash_set is None:
        return jsonify({'ready': False})
    return jsonify({'ready': True, 'dataset': _dataset_block()})


@api.route('/check/<hash_value>')
def check_legacy(hash_value):
    """Retired MD5-only GET route; kept until ticket 13, on-demand import."""
    from nsrllookup import NSRLLookup

    validate = re.finditer(r'(?=(\b[A-Fa-f0-9]{32}\b))', hash_value.upper())
    validated_input = [match.group(1) for match in validate]

    if validated_input:
        nsrl = NSRLLookup()
        digest = validated_input.pop()
        nsrl.add_hash_only(digest)
        result = nsrl.run_query()

        if digest in result['known']:
            return jsonify({'result': 'true'})
        else:
            return jsonify({'result': 'false'})
    else:
        return jsonify({'result': 'invalid hash format'})


if __name__ == '__main__':
    serve(api,
          host='0.0.0.0',
          port=5000)
