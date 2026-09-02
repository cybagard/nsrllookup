"""Seam 1: the HTTP layer, driven through the application's test client.

These drive ``POST /check`` and ``/health`` end-to-end -- the new multi-
algorithm, provenance-carrying successor to the legacy MD5-only
``test_hash_lookup.py``. A fixture **Hash Set** is installed with
``app.configure`` for each case; the **Audit Trail** (ticket 09) will be
asserted through this same seam, black-boxed as a side effect.
"""

import json

import pytest

import app
from hasheset import Provenance
import hasheset
from lookup import look_up

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
UNKNOWN_MD5 = "2977520A5C5FAAD2286D58675E400412"


@pytest.fixture
def provisioned(tmp_path):
    """Install a fixture Hash Set so the routes answer against real data."""
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
         {"crc32": "2E19F1E7", "md5": KNOWN_MD5, "md5sha1": None,
           "sha1": None, "sha256": None, "filename": "known.bin"},
        ])
    hset = hasheset.provision(path,
              Provenance("modern", "2026.03.1", ["2026.06.1"]))
    app.configure(hset)
    yield hset
    app.configure(None)


@pytest.fixture
def unconfigured():
    """No Hash Set loaded, so /health is not-ready and /check is 503."""
    app.configure(None)
    yield
    app.configure(None)


def test_check_returns_one_result_per_digest(client, provisioned):
    response = client.post('/check',
          json={'algorithm': 'md5',
                 'hashes': [KNOWN_MD5, UNKNOWN_MD5]})
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    results = data['results']
    assert len(results) == 2
    by_digest = {r['digest']: r for r in results}
    assert by_digest[KNOWN_MD5]['status'] == 'known'
    assert by_digest[UNKNOWN_MD5]['status'] == 'unknown'
    assert by_digest[KNOWN_MD5]['algorithm'] == 'md5'


def test_well_formed_request_is_200_with_per_item_invalid(client, provisioned):
    response = client.post('/check',
          json={'algorithm': 'md5',
                 'hashes': [KNOWN_MD5, "not-a-digest"]})
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    by_digest = {r['digest']: r for r in data['results']}
    assert by_digest[KNOWN_MD5]['status'] == 'known'
    assert by_digest["NOT-A-DIGEST"]['status'] == 'invalid'


def test_unsupported_algorithm_is_request_level_rejection(client, provisioned):
    response = client.post('/check',
          json={'algorithm': 'crc32', 'hashes': [KNOWN_MD5]})
    assert response.status_code == 400
    assert 'results' not in json.loads(response.get_data(as_text=True))


def test_malformed_body_is_request_level_rejection(client, provisioned):
    response = client.post('/check', data="not json",
          content_type='application/json')
    assert response.status_code == 400
    assert 'results' not in json.loads(response.get_data(as_text=True))


def test_digests_normalised_to_uppercase(client, provisioned):
    response = client.post('/check',
          json={'algorithm': 'md5', 'hashes': [KNOWN_MD5.lower()]})
    data = json.loads(response.get_data(as_text=True))
    assert data['results'][0]['digest'] == KNOWN_MD5
    assert data['results'][0]['status'] == 'known'


def test_results_carry_full_provenance(client, provisioned):
    response = client.post('/check',
          json={'algorithm': 'md5', 'hashes': [KNOWN_MD5]})
    data = json.loads(response.get_data(as_text=True))
    dataset = data['results'][0]['dataset']
    assert dataset == {'set': 'modern', 'release': '2026.03.1',
                       'deltas': ['2026.06.1']}


def test_health_reports_loaded_provenance(client, provisioned):
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data['ready'] is True
    assert data['dataset'] == {'set': 'modern', 'release': '2026.03.1',
                                   'deltas': ['2026.06.1']}


def test_health_not_ready_without_hash_set(client, unconfigured):
    response = client.get('/health')
    assert response.status_code == 200
    assert json.loads(response.get_data(as_text=True))['ready'] is False


def test_check_503_when_hash_set_not_provisioned(client, unconfigured):
    response = client.post('/check',
          json={'algorithm': 'md5', 'hashes': [KNOWN_MD5]})
    assert response.status_code == 503
