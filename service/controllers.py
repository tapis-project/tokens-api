import copy
import traceback
import uuid
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask import request
from flask_restful import Resource
from openapi_core.shortcuts import RequestValidator
from openapi_core.wrappers.flask import FlaskOpenAPIRequest
from common.config import conf
from common import auth, utils, errors

from service.auth import check_extra_claims, check_authz_private_keypair, generate_private_keypair_in_sk, t
from service.models import TapisAccessToken, TapisRefreshToken
from service import tenants


# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)


class TokensResource(Resource):
    """
    Work with Tapis Tokens
    """
    def post(self):
        logger.debug("top of  POST /tokens")
        validator = RequestValidator(utils.spec)
        validated = validator.validate(FlaskOpenAPIRequest(request))
        if validated.errors:
            raise errors.ResourceError(msg=f'Invalid POST data: {validated.errors}.')
        validated_body = validated.body
        # this raises an exception if the claims are invalid -
        if hasattr(validated_body, 'claims'):
            check_extra_claims(request.json.get('claims'))
            # set it to the raw request's claims object which is an arbitrary python dictionary
            validated_body.claims = request.json.get('claims')
        try:
            token_data = TapisAccessToken.get_derived_values(validated_body)
        except Exception as e:
            logger.error(f"Got exception trying to compute get_derived_values() for validated body; e: {e}")
            raise errors.AuthenticationError("Unable to create token. Please contact system administrator.")
        access_token = TapisAccessToken(**token_data)
        try:
            access_token.sign_token()
        except Exception as e:
            logger.error(f"Got exception trying to sign token! Exception: {e}")
            raise errors.AuthenticationError("Unable to sign token. Please contact system administrator.")

        result = {'access_token': access_token.serialize}

        # refresh token --
        if hasattr(validated_body, 'generate_refresh_token') and validated_body.generate_refresh_token:
            if hasattr(validated_body, 'refresh_token_ttl'):
                token_data['refresh_token_ttl'] = validated_body.refresh_token_ttl
            refresh_token = TokensResource.get_refresh_from_access_token_data(token_data, access_token)
            result['refresh_token'] = refresh_token.serialize
        return utils.ok(result=result, msg="Token generation successful.")

    def put(self):
        logger.debug("top of  PUT /tokens")
        validator = RequestValidator(utils.spec)
        validated = validator.validate(FlaskOpenAPIRequest(request))
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
        # except that refresh tokens do not have `delegation`, `target_site`, or any extra claims, and they do have
        # an `access_token` attr:
        token_data.pop('delegation')
        token_data.pop('target_site_id', None)
        token_data['access_token'] = access_token.claims_to_dict()
        token_data['access_token'].pop('exp')
        token_data.pop('delegation_sub', None)
        token_data.pop('extra_claims', None)
        # record the requested ttl for the token so that we can use it to generate a token of equal length
        # at refresh
        token_data['access_token']['ttl'] = token_data['ttl']
        logger.debug(f"instantiating refresh token with token_data: {token_data}")
        refresh_token_data = TapisRefreshToken.get_derived_values(token_data)
        refresh_token = TapisRefreshToken(**refresh_token_data)
        refresh_token.sign_token()
        return refresh_token


class SigningKeysResource(Resource):
    """
    Generate a new public/private key pair for token signatures.
    """

    def put(self):
        logger.debug("top of  PUT /tokens/keys")
        validator = RequestValidator(utils.spec)
        validated = validator.validate(FlaskOpenAPIRequest(request))
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
        for tenant in tenants.tenants:
            if tenant.tenant_id == tenant_id:
                tenant.private_key = private_key


