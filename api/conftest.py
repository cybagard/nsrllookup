import os

import pytest

LIVE = os.environ.get("NSRLLOOKUP_LIVE")


@pytest.fixture
def client():
    from app import api

    c = api.test_client()
    c.testing = True
    return c


def pytest_addoption(parser):
    parser.addoption(
          "--live",
          action="store_true",
          default=False,
          help="run tests that require a live nsrlsvr / Hash Set",
     )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live") or LIVE:
        return
    skip = pytest.mark.skip(reason="requires a live Hash Set; pass --live to enable")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
