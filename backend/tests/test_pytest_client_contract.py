"""Shared pytest client must never mutate requests or fabricate domain data."""
from fastapi.testclient import TestClient


def test_shared_client_is_plain_testclient(client):
    """Generic tests receive the exact TestClient type and no graduation state."""
    assert type(client) is TestClient
    assert not hasattr(client, "_active_batch_id")
    assert not hasattr(client, "_archive_previews")
