import pytest


@pytest.fixture
def client():
    from app import api

    c = api.test_client()
    c.testing = True
    return c
