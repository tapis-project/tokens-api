import pytest
import json
from unittest import TestCase
from service.api import app

# These tests are intended to be run locally.

@pytest.fixture
def client():
    app.debug = True
    return app.test_client()


def test_invalid_post(client):
    with client:
        response = client.post("http://localhost:5000/tokens")

        assert response.status_code == 400


def test_valid_post(client):
    with client:
        payload = {
            'token_tenant_id': 'dev',
            'token_type': 'service',
            'token_username': 'jstubbs'
        }

        response = client.post(
            "http://localhost:5000/tokens",
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200


def test_get_refresh_token(client):
    payload = {
        "token_tenant_id": "dev",
        "token_type": "service",
        "token_username": "jstubbs",
        "generate_refresh_token": True
    }

    response = client.post(
        "http://localhost:5000/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert "refresh_token" in response.json['result'].keys()
    refresh_token = response.json['result']['refresh_token']['refresh_token']
    access_token = response.json['result']['access_token']['access_token']

    payload2 = {
        "tenant_id": "dev",
        "refresh_token": refresh_token
    }

    response2 = client.put(
        "http://localhost:5000/tokens",
        data=json.dumps(payload2),
        content_type='application/json'
    )

    assert "refresh_token" in response2.json['result'].keys()
    assert "access_token" in response2.json['result'].keys()
    assert refresh_token != response2.json['result']['refresh_token']
    assert access_token != response2.json['result']['access_token']

def test_bad_refresh_token_gives_correct_error(client):
    payload = {
        "tenant_id": "dev",
        "refresh_token": "bad"
    }

    response = client.put(
        "http://localhost:5000/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )

    assert response.status_code == 400
