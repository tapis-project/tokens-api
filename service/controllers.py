import copy
from email import header
import resource
import traceback
import uuid
import json
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask import request
from flask_restful import Resource
import requests
from openapi_core import openapi_request_validator
from openapi_core.contrib.flask import FlaskOpenAPIRequest
from tapisservice.config import conf
from tapisservice import auth, errors
from tapisservice.tapisflask import utils

from service.auth import check_extra_claims, check_authz_private_keypair, generate_private_keypair_in_sk, t
from service.models import TapisAccessToken, TapisRefreshToken
from service import tenants


# get the logger instance -
from tapisservice.logs import get_logger
logger = get_logger(__name__)


class TokensResource(Resource):
    """
    Work with Tapis Tokens
    """
    def post(self):
        logger.debug("top of POST /tokens")
        try:
            # This is a decently ugly hack.
            # Issue:
            # Spec declares createToken claims as an free object. https://github.com/python-openapi/openapi-core/issues/430
            # This unfortunately does not validate properly.
            # Solution Attempts:
            # - Move to 0.16.1 as it's fixed. Dataclasses are tossed for models and the validated object would not be accessible
            #   in the way we currently use it. validated.body would be validated['body']. I don't wanna break the codebases.
            # - 0.17.0 also has issues. New is 0.18.0, I haven't tried it yet. Could be a solution.
            # - We could also just not validate the claims object. Nah.
            # Solution:
            # Pop claims from the request object, validate, then put it back in. This is what we're doing.
            # To note:
            # - Modifying request.data or request.json does nothing as FlaskOpenAPIRequest.super() runs request.get_data(as_text=True)
            #   and that reads unbuffered data. I attempted to override this function, but it's essential to the request object.
            # - End solution was to override FlaskOpenAPIRequest.body to return request.data.
            # - Meaning we pop claims, and add them back to the validated object afterwards in order to make no changes to any other code.

            # Override body to return request.data
            @property
            def custom_body(self, *args, **kwargs):
                return self.request.data
            FlaskOpenAPIRequest.body = custom_body

            # Regular logic
            # Pop claims and set request.data to data without claims
            request_json_without_claims = copy.deepcopy(request.json)
            popped_claims = None
            if 'claims' in request_json_without_claims:
                popped_claims = request_json_without_claims.get('claims')
                del request_json_without_claims['claims']
            request.data = json.dumps(request_json_without_claims)

            # debug logs
            # logger.debug(f"request.json: {request.json}")
            # logger.debug(f"request.popped: {request.json.get('claims')}")
            # logger.debug(f"request.data: {request.data}")

            validated = openapi_request_validator.validate(utils.spec, FlaskOpenAPIRequest(request))

            # Add claims back in
            logger.debug(f"validated: {validated}")
            if popped_claims:
                validated.body.claims = popped_claims
        except Exception as e:
            logger.error(f"Got exception trying to validate request: {e}")
            raise errors.ResourceError(msg=f'Invalid POST data: {e}.')
        
        if validated.errors:
            raise errors.ResourceError(msg=f'Invalid POST data: {validated.errors}.')
        validated_body = validated.body
        try:
            token_tenant_id = validated_body.token_tenant_id
        except:
            raise errors.ResourceError(msg=f'Invalid POST data: token_tenant_id is required.')
        if validated_body.account_type == 'service':
            if not hasattr(validated_body, 'target_site_id'):
                raise errors.ResourceError(msg="Invalid POST data: target_site_id required for creating tokens of type 'service'.")
        logger.debug(f"got token_tenant_id: {token_tenant_id}")
        if not token_tenant_id in conf.tenants:
            raise errors.ResourceError(msg=f'Invalid POST data: token_tenant_id ({token_tenant_id}) is not served by this Tokens API. tenants served: {conf.tenants}')
        # this raises an exception if the claims are invalid -
        if hasattr(validated_body, 'claims'):
            check_extra_claims(request.json.get('claims'))
            # set it to the raw request's claims object which is an arbitrary python dictionary
            validated_body.claims = request.json.get('claims')
        logger.debug(f"got validated_body claims")
        try:
            token_data = TapisAccessToken.get_derived_values(validated_body)
        except Exception as e:
            logger.error(f"Got exception trying to compute get_derived_values() for validated body; e: {e}")
            raise errors.AuthenticationError("Unable to create token. Please contact system administrator.")
        access_token = TapisAccessToken(**token_data)
        logger.debug("access token created")
        try:
            access_token.sign_token()
        except Exception as e:
            logger.error(f"Got exception trying to sign token! Exception: {e}")
            raise errors.AuthenticationError("Unable to sign token. Please contact system administrator.")
        logger.debug("access token signed")
        result = {'access_token': access_token.serialize}

        # refresh token --
        if hasattr(validated_body, 'generate_refresh_token') and validated_body.generate_refresh_token:
            logger.debug("generating refresh token")
            if hasattr(validated_body, 'refresh_token_ttl'):
                token_data['refresh_token_ttl'] = validated_body.refresh_token_ttl
            
            refresh_token = TokensResource.get_refresh_from_access_token_data(token_data, access_token)
            result['refresh_token'] = refresh_token.serialize
            logger.debug("refresh token generated ")
        logger.debug("returning token response")
        return utils.ok(result=result, msg="Token generation successful.")

    def put(self):
        logger.debug("top of  PUT /tokens")
        validated = openapi_request_validator.validate(utils.spec, FlaskOpenAPIRequest(request))
        if validated.errors:
            raise errors.ResourceError(msg=f'Invalid PUT data: {validated.errors}.')
        refresh_token = validated.body.refresh_token
        logger.debug(f"type(refresh_token) = {type(refresh_token)}")
        try:
            refresh_token_data = auth.validate_token(refresh_token)
        except errors.AuthenticationError:
            raise errors.ResourceError(msg=f'Invalid PUT data: {request}.')

        # get the original access_token data from within the decoded refresh_token
        token_data = refresh_token_data['tapis/access_token']
        token_data.pop('tapis/token_type')
        token_data['exp'] = TapisAccessToken.compute_exp(token_data['ttl'])
        token_data['jti'] = str(uuid.uuid4())
        # create a dictionary of data that can be used to instantiate access and refresh tokens; the constructors
        # require variable names that do not include the Tapis prefix, so we need to remove that -
        new_token_data = { 'jti': token_data.pop('jti'),
                           'iss': token_data.pop('iss'),
                           'sub': token_data.pop('sub'),
                           'tenant_id': token_data.pop('tapis/tenant_id'),
                           'username': token_data.pop('tapis/username'),
                           'account_type': token_data.pop('tapis/account_type'),
                           'ttl': token_data.pop('ttl'),
                           'exp': token_data.pop('exp'),
                           'delegation': token_data.pop('tapis/delegation'),
                           'delegation_sub': token_data.pop('tapis/delegation_sub', None),
                           'extra_claims': token_data
                           }
        access_token = TapisAccessToken(**new_token_data)
        access_token.sign_token()

        # add the original refresh token's initial_ttl claim as the ttl for the new refresh token
        new_token_data['refresh_token_ttl'] = refresh_token_data['tapis/initial_ttl']
        refresh_token = TokensResource.get_refresh_from_access_token_data(new_token_data, access_token)
        result = {'access_token': access_token.serialize,
                  'refresh_token': refresh_token.serialize
                  }
        return utils.ok(result=result, msg="Token generation successful.")

    @classmethod
    def get_refresh_from_access_token_data(cls, token_data, access_token):
        """
        Generate a refresh token from access token data as a dictionary and the access_token object. 
        :param token_data: dict
        :param access_token: TapisAccessToken
        :return: TapisRefreshToken, signed
        """
        logger.debug("top of get_refresh_from_access_token_data()")
        logger.debug(f"token_data:{token_data}; access_token: {access_token}")
        # refresh tokens have all the same attributes as the associated access token (and same values)
        # except that refresh tokens do not have `delegation`, `target_site`, or any extra claims, 
        # they have a different JTI, and they do have an `access_token` attr:
        token_data.pop('delegation')
        token_data.pop('target_site_id', None)
        token_data['access_token'] = access_token.claims_to_dict()
        token_data['access_token'].pop('exp')
        token_data.pop('delegation_sub', None)
        token_data.pop('extra_claims', None)
        # record the requested ttl for the token so that we can use it to generate a token of equal length
        # at refresh
        token_data['access_token']['ttl'] = token_data['ttl']        
        refresh_token_data = TapisRefreshToken.get_derived_values(token_data)
        logger.debug(f"instantiating refresh token with refresh_token_data: {refresh_token_data}")
        refresh_token = TapisRefreshToken(**refresh_token_data)
        refresh_token.sign_token()
        return refresh_token


class RevokeTokensResource(Resource):
    """
    Revoke a Tapis JWT.
    """
    def post(self):
        logger.debug("top of POST /tokens/revoke")
        validated = openapi_request_validator.validate(utils.spec, FlaskOpenAPIRequest(request))
        if validated.errors:
            raise errors.ResourceError(msg=f'Invalid POST data: {validated.errors}.')
        validated_body = validated.body
        token_str = validated.body.token
        try:
            token_data = auth.validate_token(token_str)
        except errors.AuthenticationError as e:
            raise errors.ResourceError(msg=f'Invalid POST data; could not validate the token: debug data: {e}.')
        # call the site-router to add the token to the revocation table
        # we always call the site-router located at our site and with the X-Tapis-Tenant and User
        # headers set to ourselves (tokens api)
        url = f'{t.base_url}/v3/site-router/tokens/revoke'
        request_tenant_id = conf.service_tenant_id
        request_user = conf.service_name
        try:
            service_token =  t.service_tokens[request_tenant_id]['access_token'].access_token
        except Exception as e:
            logger.error(f"Could not get the token's service access token; details: {e}")
            raise errors.ResourceError(msg='Service error revoking token: contact service admins.')
        headers = {
            'X-Tapis-Tenant': request_tenant_id, 
            'X-Tapis-User': request_user,
            'X-Tapis-Token': service_token,
        }
        try:
            rsp = requests.post(url, headers=headers, json={"token": token_str})
            rsp.raise_for_status()
        except Exception as e:
            logger.info(f"Got exception in call to site-router; exception: {e}")
            raise errors.ResourceError(msg=f'Error contacting Tapis to revoke token; details: {e}')
        return utils.ok(result='', msg=f"Token {token_data['jti']} has been revoked.")


class SigningKeysResource(Resource):
    """
    Generate a new public/private key pair for token signatures.
    """

    def put(self):
        logger.debug("top of  PUT /tokens/keys")
        validated = openapi_request_validator.validate(utils.spec, FlaskOpenAPIRequest(request))
        if validated.errors:
            raise errors.ResourceError(msg=f'Invalid PUT data: {validated.errors}.')
        tenant_id = validated.body.tenant_id
        logger.debug(f"calling check_authz_private_keypair with tenant_id {tenant_id}")
        check_authz_private_keypair(tenant_id)
        logger.debug("returned from check_authz_private_keypair; updating keys...")
        private_key, public_key = generate_private_keypair_in_sk(tenant_id)
        # update the tenant definition with the new public key
        logger.debug(f"making request to update tenant {tenant_id} with new public key.")
        try:
            t.tenants.update_tenant(tenant_id=tenant_id, public_key=public_key)
        except Exception as e:
            logger.error(f"Got exception trying to update tenant with new public key. Tenants API"
                         f"and SK are now out of sync!! SHOULD BE LOOKED AT IMMEDIATELY. "
                         f"Exception: {e}")
            raise errors.ResourceError(msg=f'Unable to update tenant definition with new public key'
                                           f'Please contact system administrators.')
        logger.info(f"tenant {tenant_id} has been updated with the new public key.")
        # update token's tenant cache with this private key for signing:
        logger.debug("updating token cache...")
        for t_id, tenant in tenants.tenants.items():
            if t_id == tenant_id:
                tenant.private_key = private_key
        result = {'public_key': public_key}
        return utils.ok(result=result, msg="Tenant signing keys update successful.")


