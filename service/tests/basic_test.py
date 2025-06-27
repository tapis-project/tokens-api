from base64 import b64encode
import pytest
import json
import requests
from unittest import TestCase
from service.api import app
from service.auth import get_tokens_tapis_client, validate_siteadmin_password
from tapisservice import auth
from tapisservice.config import conf

# input just for testing::
import tapipy
import uuid
from service.models import AccessTokenData, TapisAccessToken
from service import tenants
from tapipy.tapis import Tapis


# These tests are intended to be run locally.

@pytest.fixture
def client():
    app.debug = True
    return app.test_client()


def test_invalid_post(client):
    with client:
        response = client.post("http://localhost:5000/v3/tokens")

        assert response.status_code == 400

def get_basic_auth_header():
    user_pass = bytes(f"tenants:{conf.allservices_password}", 'utf-8')
    return {'Authorization': 'Basic {}'.format(b64encode(user_pass).decode()),
            'X-Tapis-Tenant': 'admin'}


def test_valid_post(client):
    with client:
        payload = {
            "token_tenant_id": "admin",
            "account_type": "service",
            "token_username": "tenants",
            "target_site_id": "admin"
        }

        response = client.post(
            "http://localhost:5000/v3/tokens",
            data=json.dumps(payload),
            content_type='application/json',
            headers=get_basic_auth_header()
        )
        print(f"response.data: {response.data}")
        assert response.status_code == 200


def test_get_refresh_token(client):
    payload = {
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        "generate_refresh_token": True,
        "target_site_id": "admin"
    }
    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers=get_basic_auth_header()
    )
    assert "refresh_token" in response.json['result'].keys()
    refresh_token = response.json['result']['refresh_token']['refresh_token']
    access_token = response.json['result']['access_token']['access_token']
    jti = response.json['result']['access_token']['jti']

    payload2 = {
        "tenant_id": "admin",
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
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        "generate_refresh_token": True,
        "claims": {"test_claim": "here it is!"},
        "target_site_id": "admin"
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers=get_basic_auth_header()
    )
    print(f"response.data: {response.data}")

    assert response.status_code == 200
    access_token = response.json['result']['access_token']['access_token']
    access_token_data = auth.validate_token(access_token)

    assert access_token_data['test_claim'] == "here it is!"


def test_custom_ttls(client):
    payload = {
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        # 4 hour access token
        "access_token_ttl": 14400,
        "generate_refresh_token": True,
        # 90 day refresh token
        "refresh_token_ttl": 7776000,
        "target_site_id": "admin"
    }
    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers=get_basic_auth_header()
    )
    assert response.status_code == 200
    assert response.json['result']['access_token']['expires_in'] == 14400
    assert response.json['result']['refresh_token']['expires_in'] == 7776000

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
    assert response2.json['result']['access_token']['expires_in'] == 14400
    assert response2.json['result']['refresh_token']['expires_in'] == 7776000

def test_custom_ttls_cannot_be_zero(client):
    payload = {
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        "access_token_ttl": 0,
        "generate_refresh_token": True,
        "refresh_token_ttl": 0,
        "target_site_id": "admin"
    }
    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers = get_basic_auth_header()
    )
    assert response.status_code == 200

    # If the ttl is set as 0 by the user, the default will be used instead
    assert response.json['result']['access_token']['expires_in'] != 0
    assert response.json['result']['refresh_token']['expires_in'] != 0

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
    assert response2.json['result']['access_token']['expires_in'] == 300
    assert response2.json['result']['refresh_token']['expires_in'] == 600

def test_custom_claims_show_up_after_refresh(client):

    # First, get an access token
    payload = {
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        "generate_refresh_token": True,
        "claims": {"test_claim": "here it is!"},
        "target_site_id": "admin"
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers=get_basic_auth_header()
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


def test_revoke_token(client):
    # generate a new access and refresh token that we can revoke 
    payload = {
        "token_tenant_id": "admin",
        "account_type": "service",
        "token_username": "tenants",
        "generate_refresh_token": True,
        "claims": {"test_claim": "here it is!"},
        "target_site_id": "admin"
    }

    response = client.post(
        "http://localhost:5000/v3/tokens",
        data=json.dumps(payload),
        content_type='application/json',
        headers=get_basic_auth_header()
    )

    assert response.status_code == 200
    access_token = response.json['result']['access_token']['access_token']
    refresh_token = response.json['result']['refresh_token']['refresh_token']

    # call the same site-router tokens is configured for
    site_router_url = f"{conf.primary_site_admin_tenant_base_url}/v3/site-router"
    # should be able to call the site-router and see that these new tokens are not revoked:
    check_endpoint = f"{site_router_url}/tokens/check"
    headers = {"x-tapis-token": access_token}
    response = requests.get(check_endpoint, headers=headers)
    print(f"response: {response.content}")
    assert response.status_code == 200

    headers = {"x-tapis-token": refresh_token}
    response = requests.get(check_endpoint, headers=headers)
    assert response.status_code == 200

    # now, revoke the tokens
    # first, revoke the refresh token -- 
    payload = {"token": refresh_token}
    response = client.post(
        "http://localhost:5000/v3/tokens/revoke",
        json=payload
    )
    assert response.status_code == 200
    # check that is has been revoked:
    response = requests.get(check_endpoint, headers=headers)
    assert response.status_code == 400

    # then, revoke the access token
    payload = {"token": access_token}
    response = client.post(
        "http://localhost:5000/v3/tokens/revoke",
        json=payload
    )
    assert response.status_code == 200
    # check that is has been revoked:
    headers = {"x-tapis-token": access_token}
    response = requests.get(check_endpoint, headers=headers)
    assert response.status_code == 400


def test_oidc_well_known_openid_configuration(client):
    primary_site_dev_tenant_base_url = 'https://' + 'dev.' + '.'.join(conf.primary_site_admin_tenant_base_url.split('.')[1:])
    print(primary_site_dev_tenant_base_url)
    with client:
        response = client.get('http://localhost:5000/v3/tokens/.well-known/openid-configuration')
        print(response.data)
        assert response.status_code == 200
        assert 'issuer' in response.json
        assert 'jwks_uri' in response.json
        # assert 'https://dev.develop.tapis.io/v3/tokens' in response.json['issuer'] # true so long as default tenant is `dev`
        assert primary_site_dev_tenant_base_url in response.json['issuer'] # true so long as default tenant is `dev`

## TODO: disabled for now. Need to change these values to get them from the environment of the test container rather than hard-coded like this. 
## decided to skip these tests for now, since there isn't a good way to get them done yet.
# def test_check_site_admin_credentials(client):
#     # if this test is failing, need to manually add a site admin to the environment being tested. 
#     # there isn't currently a way to do it through the cli
   
#     result = None
#     result = validate_siteadmin_password('admin', 'username', 'password')
#     assert result==True


# def test_check_site_admin_incorrect_credentials(client):
#     # if this test is failing, need to manually add a site admin to the environment being tested. 
#     # there isn't currently a way to do it through the cli
    
#     result = None
#     try:
#         result = validate_siteadmin_password('admin', 'username', 'wrong_password')
#         raise # this is supposed to fail, so if we get here it's a problem
#     except Exception as e:
#         pass # failing won't have a valid response since it's an internal method. Just pass on excpetions
#     assert result != True # just in case

    
# def test_generate_site_admin_token(client):
#     # create a dummy site admin account to use
#     with client:
#         b_auth = b64encode(bytes("username:password", 'utf-8')).decode()
#         headers = {
#             "Authorization": f"Basic {b_auth}",
#             "Content-Type": "application/json"
#         }
#         payload = {
#             "token_tenant_id": "admin",
#             "account_type": "user",
#             "token_username": "kprice"
#         }

#         response = client.post(
#             "https://admin.kprice02.tacc.utexas.edu/v3/tokens",
#             json=payload,
#             headers=headers
#         )
#         print(f'had headers:: {headers}')
#         print(f"response.data: {response.data}")
#         assert response.status_code == 200
#         # TODO:: check that the token exists? or verify it??
        

# def test_service_token_cant_create_service_token(client):
#     # services cannot use their token to create tokens for other services (in an admin tenant)
#     pass

# def test_service_token_cant_create_user_in_admin(client):
#     # services cannot use their token to create "user" tokens in the admin tenant
#     pass

# def test_service_token_cant_create_user_token_without_role(client):
#     # services cannot use their token to create tokens for users in any user tenant except if they have the {tenant}_TOKEN_GENERATOR role.
#     pass

  

