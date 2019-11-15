from common.config import conf
from common import errors as common_errors
from flask import g, request
from service.errors import InvalidTokenClaimsError
from service.models import TapisAccessToken

# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)

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
                                              f"as it is a standarg Tapis claim.")
    else:
        # TODO - implement auth via SK
        raise NotImplementedError("The security kernel is not available.")
