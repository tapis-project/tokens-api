from common.auth import get_service_tapy_client
from common.config import conf
from common import errors as common_errors
from flask import g, request
from service.errors import InvalidTokenClaimsError
from service.models import AccessTokenData, TapisAccessToken
from service import get_tenant_config

# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)

logger.debug("top of auth.py")

# 10 years TTL
SERVICE_TOKEN_TTL = 60*60*24*365*10

# this is the Tapis client that tokens will use for interacting with other services, such as the security kernel.
token_tenant = get_tenant_config(tenant_id=conf.service_tenant_id)
logger.debug('got token_tenant')
d = AccessTokenData(token_tenant_id=conf.service_tenant_id, token_username=conf.service_name, account_type = 'service')
d.access_token_ttl =  SERVICE_TOKEN_TTL
token_data = TapisAccessToken.get_derived_values(d)
jwt = TapisAccessToken(**token_data)
jwt.sign_token()
logger.debug("generated and signed tokens service JWT.")
t = get_service_tapy_client(jwt=jwt)
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
        if request.method == 'POST' or request.method == 'PUT':
            pass
            # do basic auth with SK and tapis client, t...


def check_extra_claims(extra_claims):
    """
    Checks whether the request is authorized to add extra_claims.
    :param extra_claims:
    :return:
    """
    logger.debug("top of check_extra_claims")
    if not conf.use_sk:
        # in dev mode when not using the security kernel, we allow all extra claims that are not part of the
        # standard tapis set
        for k,_ in extra_claims.items():
            if k in TapisAccessToken.standard_tapis_access_claims:
                raise InvalidTokenClaimsError(f"passing claim {k} as an extra_claim is not allowed, "
                                              f"as it is a standard Tapis claim.")
    else:
        # TODO - implement auth via SK
        raise NotImplementedError("The security kernel is not available.")
