# coding: UTF-8

"""Live-server integration tests (the legacy MD5-only /check route).

These drive a live nsrlsvr backing the Hash Set and are gated behind the
``live`` marker -- off by default so a bare ``pytest`` run is green with no
running server. Enable with ``--live`` (or ``NSRLLOOKUP_LIVE=1``).
"""

import json

import pytest


pytestmark = pytest.mark.live


def test_hash_lookup_status_code(client):
    response = client.get('/check/ad7b9c14083b52bc532fba5948342b98')
    assert response.status_code == 200


def test_hash_lookup_respone_data_lower(client):
    response = client.get('/check/ad7b9c14083b52bc532fba5948342b98')
    data = json.loads(response.get_data(as_text=True))
    assert data['result'] == 'true'


def test_hash_lookup_respone_data_upper(client):
    response = client.get('/check/AD7B9C14083B52BC532FBA5948342B98')
    data = json.loads(response.get_data(as_text=True))
    assert data['result'] == 'true'


def test_hash_lookup_respone_data_negative(client):
    response = client.get('/check/2977520a5c5faad2286d58675e400412')
    data = json.loads(response.get_data(as_text=True))
    assert data['result'] == 'false'


def test_hash_lookup_respone_data_invalid_format(client):
    response = client.get('/check/2977520a5c5faad2286d58675e4004122977520a5c5faad2286d58675e400412')
    data = json.loads(response.get_data(as_text=True))
    assert data['result'] == 'invalid hash format'


def test_hash_lookup_respone_data_invalid_format_1(client):
    response = client.get('/check/2977520')
    data = json.loads(response.get_data(as_text=True))
    assert data['result'] == 'invalid hash format'
