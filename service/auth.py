import tapy
import uuid
from common.auth import get_service_tapy_client, authentication
from common.config import conf
from common import errors as common_errors
from flask import g, request
from service.errors import InvalidTokenClaimsError
from service.models import AccessTokenData, TapisAccessToken
from service import tenants

# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)

logger.debug("top of auth.py")

# 10 years TTL
SERVICE_TOKEN_TTL = 60*60*24*365*10

# this is the Tapis client that tokens will use for interacting with other services, such as the security kernel.
token_tenant = tenants.get_tenant_config(tenant_id=conf.service_tenant_id)
logger.debug('got token_tenant')
d = AccessTokenData(jti=uuid.uuid4(), token_tenant_id=conf.service_tenant_id, token_username=conf.service_name, account_type = 'service')
d.access_token_ttl = SERVICE_TOKEN_TTL
token_data = TapisAccessToken.get_derived_values(d)
jwt = TapisAccessToken(**token_data)
raw_jwt = jwt.sign_token()
logger.debug("generated and signed tokens service JWT.")
t = get_service_tapy_client(jwt=raw_jwt)
logger.debug("got tapy client for tokens.")

def authn_and_authz():
    """
    Entry point for checking authentication and authorization
    :return:
    """
    # first check whether the request is even a valid
    if hasattr(request, 'url_rule'):
        logger.debug("request.url_rule: {}".format(request.url_rule))
        if hasattr(request.url_rule, 'rule'):
            logger.debug("url_rule.rule: {}".format(request.url_rule.rule))
        else:
            logger.info("url_rule has no rule.")
            raise common_errors.BaseTapisError(
                "Invalid request: the API endpoint does not exist or the provided HTTP method is not allowed.", 405)
    else:
        logger.info("Request has no url_rule")
        raise common_errors.BaseTapisError(
            "Invalid request: the API endpoint does not exist or the provided HTTP method is not allowed.", 405)
    # if we are using the SK, we require basic auth on generating tokens (access or refresh).
    if conf.use_sk:
        if request.method == 'POST': # note: PUT (i.e. refresh) does NOT require additional auth
            # check for basic auth header:
            parts = get_basic_auth_parts()
            if parts:
                # check that request POST data contains tenant_id and username and that the username matches that
                # in the HTTP Basic Auth header; otherwise, service could impersonate other services/tenants.
                try:
                    tenant_id = request.get_json().get('token_tenant_id')
                    username = request.get_json().get('token_username')
                except Exception as e:
                    logger.info(f"Got exception trying to parse JSON from request; e: {e}; type(e):{type(e)}")
                    raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?')
                if not username == parts['username']:
                    raise common_errors.AuthenticationError('Invalid POST data -- username does not match auth header.')
                if not tenant_id:
                    raise common_errors.AuthenticationError('Invalid POST data -- tenant_id missing from POST data.')
                # do basic auth with SK and tapis client.
                logger.debug("got parts, checking service password..")
                check_service_password(tenant_id, parts['username'], parts['password'])
                return True
            else:
                # check for a Tapis token -- this call should put username and tenant on the g object
                logger.debug("did not get parts, checking for tapis token..")
                authentication()
                # now, check with SK that service is authorized for the action. Token generation is controlled by a
                # specific role corresponding to the tenant
                try:
                    tenant_id = request.get_json().get('token_tenant_id')
                except Exception as e:
                    logger.info(f"Got exception trying to parse JSON from Tapis token request; e: {e}; type(e):{type(e)}")
                    raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?')
                role_name = f'{tenant_id}_token_generator'
                try:
                    users = t.sk.getUsersWithRole(tenant='master', roleName=role_name)
                except Exception as e:
                    msg = f'Got an error calling the SK to get users with role {role_name}. Exception: {e}'
                    logger.error(msg)
                    raise common_errors.PermissionsError(
                        msg=f'Could not verify permissions with the Security Kernel; additional info: {e}')
                if g.username not in users.names:
                    logger.info(f"user {g.username} was not in role {role_name}. raising permissions error.")
                    raise common_errors.PermissionsError(msg=f'Not authorized to generate tokens in tenant {tenant_id}.')
                return True


def get_basic_auth_parts():
    """
    Checks if the request contains the necessary headers for basic authentication, and if so, returns a dictionary
    containing the tenant_id, username, and password. Otherwise, returns None.
    NOTE: This method DOES NOT actually validate the password. That is the role of the caller.
    :return: (dict or None) - Either a python dictionary with the following keys:
        * tenant_id: The tenant_id to use to check this basic auth.
        * username: the "username" field of the Basic Auth header (decoded).
        * password: the "password" field of the Basic Auth header (decoded).
    """
    logger.debug("top of get_basic_auth_parts")
    if 'Authorization' in request.headers:
        logger.debug("request contained a basic auth header... building parts.")
        auth = request.authorization
        logger.debug(f"auth = {auth}")
        try:
            return {'username': auth.username,
                    'password': auth.password}
        except Exception as e:
            logger.error(f"Got exception trying to retrieve the username and password from the headers. e: {e}")
            raise common_errors.AuthenticationError('Unable to parse HTTP Basic Authorization header.')
    return None


def check_service_password(tenant_id, username, password):
    # update 3/2020: "password" is now the secret name in the SK for all service passwords, as the user and
    # tenant are now encoded in the path, passed in as specific attributes to the API call.
    secret_name = 'password'
    # when use_allservices_password is True, we check  single password for all services (as a convenience)
    # update 3/2020: use_allservices_password is not slated for removal.
    # if conf.use_allservices_password:
    #     secret_name = 'password'
    #     # secret_name = f'{tenant_id}+allservices+password'
    logger.debug(f"top of check_service_password: tenant_id: {tenant_id}; username: {username}; password: {password}")
    try:
        result = t.sk.readSecret(secretType='service', secretName=secret_name, tenant=tenant_id, user=username)
    except tapy.errors.InvalidInputError as e:
        logger.info(f"Got InvalidInputError trying to check service password inside SK secretMap. Exception: {e}")
        raise common_errors.AuthenticationError(msg='Invalid service account/password combination. Service account may not be registered with SK.')
    except Exception as e:
        logger.debug(f"got exception from call to readSecret; e: {e}; type(e): {type(e)}")
        if type(e) == common_errors.AuthenticationError:
            raise e
        logger.error(f'Got exception trying to retrieve the secret {secret_name} from SK. Exception: {e}')
        raise common_errors.AuthenticationError(msg='Tokens API got an error trying to contact SK to validate service secret.')
    try:
        real_pass = result.secretMap.password
    except Exception as e:
        logger.error(f"Got exception trying to pull service password from SK secretMap. Exception: {e}")
        raise common_errors.AuthenticationError(msg='Tokens API was unable to validate service secret with SK.')
    if not real_pass == password:
        raise common_errors.AuthenticationError('Invalid password.')


def check_extra_claims(extra_claims):
    """
    Checks whether the request is authorized to add extra_claims.
    :param extra_claims:
    :return:
    """
    logger.debug("top of check_extra_claims")
    # do not alow extra_claims to override claims that are part of the standard tapis result set:
    for k, _ in extra_claims.items():
        if k in TapisAccessToken.standard_tapis_access_claims:
            raise InvalidTokenClaimsError(f"passing claim {k} as an extra_claim is not allowed, "
                                          f"as it is a standard Tapis claim.")
    if not conf.use_sk:
    # in dev mode when not using the security kernel, we allow all extra claims that are not part of the
    # standard tapis set
        pass
    else:
        # TODO - implement auth via SK
        pass
        # raise NotImplementedError("The security kernel is not available.")
