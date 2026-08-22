"""Liveness test: the existing /ping route still responds."""


def test_ping(client):
    response = client.get('/ping')
    assert response.status_code == 200
