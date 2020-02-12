import pytest
import json
from unittest import TestCase
from service.api import app
from common import auth

# These tests are intended to be run locally.

@pytest.fixture
def client():
    app.debug = True
    return app.test_client()


def test_invalid_post(client):
    with client:
        response = client.post("http://localhost:5000/v3/tokens")

        assert response.status_code == 400


def test_valid_post(client):
    with client:
        payload = {
            'token_tenant_id': 'dev',
            'account_type': 'service',
            'token_username': 'files',

        }

        response = client.post(
            "http://localhost:5000/v3/tokens",
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200


def test_get_refresh_token(client):
    payload = {
        "token_tenant_id": "dev",
        "account_type": "service",
        "token_username": "jstubbs",
        "generate_refresh_token": True
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert "refresh_token" in response.json['result'].keys()
    refresh_token = response.json['result']['refresh_token']['refresh_token']
    access_token = response.json['result']['access_token']['access_token']
    jti = response.json['result']['access_token']['jti']

    payload2 = {
        "tenant_id": "dev",
        "refresh_token": refresh_token
    }

    response2 = client.put(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload2),
        content_type='application/json'
    )
    jti2 = response2.json['result']['access_token']['jti']
    assert "refresh_token" in response2.json['result'].keys()
    assert "access_token" in response2.json['result'].keys()
    assert refresh_token != response2.json['result']['refresh_token']
    assert access_token != response2.json['result']['access_token']
    assert jti != jti2


def test_bad_refresh_token_gives_correct_error(client):
    payload = {
        "tenant_id": "dev",
        "refresh_token": "bad"
    }

    response = client.put(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_custom_claims_show_up_in_access_token(client):
    payload = {
        "token_tenant_id": "dev",
        "account_type": "service",
        "token_username": "jstubbs",
        "generate_refresh_token": True,
        "claims": {"test_claim": "here it is!"}
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )

    assert response.status_code == 200
    access_token = response.json['result']['access_token']['access_token']
    access_token_data = auth.validate_token(access_token)

    assert access_token_data['test_claim'] == "here it is!"


def test_custom_ttls(client):
    payload = {
        "token_tenant_id": "dev",
        "account_type": "service",
        "token_username": "jstubbs",
        # 4 hour access token
        "access_token_ttl": 14400,
        "generate_refresh_token": True,
        # 90 day refresh token
        "refresh_token_ttl": 7776000,
    }
    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    response.json['result']['access_token']['expires_in'] == 14400
    response.json['result']['refresh_token']['expires_in'] == 7776000

    refresh_token = response.json['result']['refresh_token']['refresh_token']

    # now, refresh the token and make sure new access and refresh have the original custom ttl's
    payload2 = {
        "refresh_token": refresh_token
    }
    response2 = client.put(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload2),
        content_type='application/json'
    )
    assert response2.status_code == 200
    response2.json['result']['access_token']['expires_in'] == 14400
    response2.json['result']['refresh_token']['expires_in'] == 7776000


def test_custom_claims_show_up_after_refresh(client):

    # First, get an access token
    payload = {
        "token_tenant_id": "dev",
        "account_type": "service",
        "token_username": "jstubbs",
        "generate_refresh_token": True,
        "claims": {"test_claim": "here it is!"}
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json'
    )

    # Check that the first access token has the custom claim
    assert response.status_code == 200
    access_token = response.json['result']['access_token']['access_token']
    access_token_data = auth.validate_token(access_token)

    assert access_token_data['test_claim'] == "here it is!"

    # Then refresh the token
    refresh_token = response.json['result']['refresh_token']['refresh_token']

    payload2 = {
        "refresh_token": refresh_token
    }

    response2 = client.put(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload2),
        content_type='application/json'
    )

    # Check the new access token
    assert response2.status_code == 200
    access_token2 = response2.json['result']['access_token']['access_token']

    # Make sure the custom claim is still there
    access_token_data2 = auth.validate_token(access_token2)

    assert access_token_data2['test_claim'] == "here it is!"


def test_cannot_override_existing_claims(client):
    pass

