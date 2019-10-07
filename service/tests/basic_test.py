import pytest

from service.models import app

@pytest.fixture
def client():
    app.debug = True
    return app.test_client()

def test_invalid_post(client):
    response = client.post("http://localhost:5000/tokens")
    assert response.status_code == 404


def test_valid_post(client):
    payload = {
        b"token_tenant_id": b"dev",
        b"token_type": b"service",
        b"token_username": b"jstubbs"
    }
    headers = {b"Content-type": b"application/json"}
    response = client.post("http://localhost:5000/tokens", data=payload, headers=headers)
    assert b"Invalid POST data" not in response.data
