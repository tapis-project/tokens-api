import copy
import traceback
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask import request
from flask_restful import Resource
from openapi_core.shortcuts import RequestValidator
from openapi_core.wrappers.flask import FlaskOpenAPIRequest
from common.config import conf
from common import auth, utils, errors

from service.auth import check_extra_claims
from service.models import TapisAccessToken, TapisRefreshToken
from service import db


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
        # this raises an exception of the claims are invalid -
        if hasattr(validated_body, 'claims'):
            check_extra_claims(request.json.get('claims'))
            # set it to the raw request's claims object which is an arbitrary python dictionary
            validated_body.claims = request.json.get('claims')
        logger.debug("extra claims check approved.")
        token_data = TapisAccessToken.get_derived_values(validated_body)
        access_token = TapisAccessToken(**token_data)
        access_token.sign_token()
        result = {}
        result['access_token'] = access_token.serialize

        # refresh token --
        if hasattr(validated_body, 'generate_refresh_token') and validated_body.generate_refresh_token:
            refresh_token = TokensResource.get_refresh_from_access_token_data(token_data, access_token)
            result['refresh_token'] = refresh_token.serialize
        return utils.ok(result=result, msg="Token generation successful.")

    def put(self):
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
        # create a dictionary of data that can be used to instantiate access and refresh tokens; the constructors
        # require variable names that do not include the Tapis prefix, so we need to remove that -
        new_token_data = { 'iss': token_data.pop('iss'),
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
        # refresh tokens have all the same attributes as the associated access token (and same values)
        # except that refresh tokens do not have `delegation`, they do have an `access_token` attr, and they
        # cannot have extra claims:
        token_data.pop('delegation')
        token_data['access_token'] = access_token.claims_to_dict()
        token_data['access_token'].pop('exp')
        token_data.pop('delegation_sub', None)
        token_data.pop('extra_claims', None)
        # record the requested ttl for the token so that we can use it to generate a token of equal length
        # at refresh
        token_data['access_token']['ttl'] = token_data['ttl']
        refresh_token_data = TapisRefreshToken.get_derived_values(token_data)
        refresh_token = TapisRefreshToken(**refresh_token_data)
        refresh_token.sign_token()
        return refresh_token
