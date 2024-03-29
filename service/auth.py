import tapipy
import uuid
from tapisservice.auth import get_service_tapis_client 
from tapisservice.tapisflask.auth import authentication, resolve_tenant_id_for_request
from tapisservice.config import conf
from tapisservice import errors as common_errors
from flask import g, request
from service.errors import InvalidTokenClaimsError
from service.models import AccessTokenData, TapisAccessToken
from service import tenants

# get the logger instance -
from tapisservice.logs import get_logger
logger = get_logger(__name__)

logger.debug("top of auth.py")

# 10 years TTL
SERVICE_TOKEN_TTL = 60*60*24*365*10

# this role is stored in the security kernel
ROLE = 'tenant_definition_updater'


def get_tokens_tapis_client():
    """
    Instantiates and returns a tapis client for the Tokens service by generating the service tokens
    using the private key associated with the admin tenant.
    """
    # generate our own service tokens ---
    # minimal data needed to create an access token:
    base_token_data = AccessTokenData(jti=uuid.uuid4(),
                                      token_tenant_id=conf.service_tenant_id,
                                      token_username=conf.service_name,
                                      account_type='service')
    # override some defaults --
    base_token_data.access_token_ttl = SERVICE_TOKEN_TTL
    # set up the service tokens object: dictionary mapping of tenant_id to token data for all
    # tenants the Tokens API will need to interact with.
    service_tokens = {t: {} for t in tenants.get_site_admin_tenants_for_service()}
    logger.debug(f"Starting to generate signed tokens for the following tenant ids: {service_tokens.keys()}")
    for tenant_id in service_tokens.keys():
        logger.debug(f"generating a service token for tenant {tenant_id}.")
        try:
            target_site_id = tenants.get_tenant_config(tenant_id=tenant_id).site_id
        except Exception as e:
            logger.error(f"was unable to retrieve config for tenant {tenant_id}; failed to generate a token.")
            raise common_errors.BaseTapyException(f"Got exception computing target site id; e:{e}")
        base_token_data.target_site_id = target_site_id
        token_data = TapisAccessToken.get_derived_values(base_token_data)
        access_token = TapisAccessToken(**token_data)
        access_token.sign_token()
        # create the "access_token" attribute pointing to the raw JWT just as tapipy does
        # in its get_tokens() methods
        access_token.access_token = access_token.jwt
        service_tokens[tenant_id]['access_token'] = access_token
        logger.debug(f"token for tenant id {tenant_id} created. ")

    our_admin_jwt = service_tokens[conf.service_tenant_id]['access_token'].access_token
    # use the convenience function from the common package to generate a service client
    # we skip token generation, since we generated our own tokens:
    t = get_service_tapis_client(tenant_id=conf.service_tenant_id,
                                 jwt=our_admin_jwt,
                                 tenants=tenants,
                                 generate_tokens=False)

    # attach our service_tokens to the client and return --
    t.service_tokens = service_tokens
    return t


def get_signing_keys_for_all_tenants_from_sk():
    """
    Retrieve all signing keys for all tenants served by this Tokens API.
    This function is called at service start up.
    """
    logger.debug('top of get_signing_keys_for_all_tenants_from_sk; retrieving tenant signing keys.')
    for _id, tenant in tenants.tenants.items():
        # need to check if this is a tenant this Tokens API serves:
        if not tenant.site_id == conf.service_site_id:
            logger.debug(f"skipping tenant_id {tenant.tenant_id} as it is owned by site {tenant.site_id} and this tokens"
                         f"API is serving site {conf.service_site_id}.")
            continue
        logger.debug(f"retrieving signing key for tenant {tenant.tenant_id}")
        tenant.private_key, _ = tenants.get_tenant_signing_keys_from_sk(t, tenant.tenant_id)


# the tapis client used by the tokens API --
t = get_tokens_tapis_client()
logger.debug("got tapipy client for tokens.")
# use tapipy client to get the signing keys from the SK at start up...
if conf.use_sk:
    logger.debug("Retrieving signing keys for all tenants from SK...")
    get_signing_keys_for_all_tenants_from_sk()


# Authentication and Authorization
# --------------------------------

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
        # if a request sets both a basic auth header AND an x-tapis-token header, we should immediately
        # throw an error:
        if 'Authorization' in request.headers and 'X-Tapis-Token' in request.headers:
            raise common_errors.BaseTapisError("Invalid request: both X-Tapis-Token and HTTP Basic Auth headers set; please set only one.")

        # first check if this is a request to update the token signing keys
        if 'tokens/keys' in request.url_rule.rule:
            # check for a Tapis token
            logger.debug("request to update token signing keys, looking for a tapis token..")
            authentication()
            # updating the token signing keys requires a special role, stored in SK. note that we are using the
            # tenant_id associated with the access token (g.tenant_id) in the check here, because the token could be
            # a user token or it could be a service token. in either case, the user must have the tenant updater role.
            # later, we also check that the tenant_id in the payload either matches g.tenant_id or that it is the
            # admin tenant for the site owning the tenant in the payload. (see check_authz_private_keypair() below)
            try:
                users = t.sk.getUsersWithRole(roleName=ROLE, tenant=g.tenant_id)
            except Exception as e:
                msg = f'Got an error calling the SK. Exception: {e}'
                logger.error(msg)
                raise common_errors.PermissionsError(
                    msg=f'Could not verify permissions with the Security Kernel; additional info: {e}')
            logger.debug(f"got users: {users}; checking if {g.username} is in role {ROLE}.")
            if g.username not in users.names:
                logger.info(f"user {g.username} was not in role {ROLE}. raising permissions error.")
                raise common_errors.PermissionsError(msg='Not authorized to modify the tenant signing keys.')
            return True

        # next, check whether this is a request to revoke a token
        if 'tokens/revoke' in request.url_rule.rule:
            # anyone with a token is currently allowed to revoke it. the only issue is whether this tokens API
            # should revoke it. 
            try:
                token_str = request.get_json().get('token')
            except Exception as e:
                logger.info(f"Got exception trying to parse JSON from request; e: {e}; type(e):{type(e)}")
                raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?')
            # for now, we allow any site to revoke any token. we can revisit this in the future
            return True


        # otherwise, this is a request to create a token (either with a service account/password (POST) or with a
        # refresh token (PUT).
        if request.method == 'POST': # note: PUT (i.e. refresh) does NOT require additional auth
            # check that request POST data contains tenant_id and username and that the username matches that
            # in the HTTP Basic Auth header; otherwise, service could impersonate other services/tenants.
            try:
                tenant_id = request.get_json().get('token_tenant_id')
                username = request.get_json().get('token_username')
            except Exception as e:
                logger.info(f"Got exception trying to parse JSON from request; e: {e}; type(e):{type(e)}")
                raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?')
            # check for basic auth header:
            parts = get_basic_auth_parts()
            if parts:
                # note that we cannot call the authentication() function in this case because there is not a token header.
                # still, we need to resolve the tenant_id for the request
                resolve_tenant_id_for_request()
                if not username == parts['username']:
                    raise common_errors.AuthenticationError('Invalid POST data -- username does not match auth header.')
                if not tenant_id:
                    raise common_errors.AuthenticationError('Invalid POST data -- tenant_id missing from POST data.')
                # do basic auth with SK and tapis client.
                logger.debug("got parts, checking service password..")
                check_service_password(tenant_id, parts['username'], parts['password'])
                logger.debug("password was valid.")
                return True
            else:
                # check for a Tapis token -- this call should put username and tenant on the g object
                logger.debug("did not get parts, checking for tapis token..")
                authentication()
                # if this is a request from a service to generate a token for itself, we do not need to check
                # the SK role.
                if username == g.username and tenant_id == g.tenant_id:
                    return True

                # otherwise, this is a request to generate a token for a subject other than the service, so we need 
                # to check with SK that the service is authorized for the action. Token generation is controlled by a
                # specific role corresponding to the tenant that the caller is trying to create the token in.

                # note: we do not allow generating tokens of type "user" in the site-admin tenant
                try:
                    account_type = request.get_json().get('account_type')
                except Exception as e:
                    logger.info(f"Got exception trying to parse JSON from Tapis token request; e: {e}; type(e):{type(e)}")
                    raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?') 
                if not account_type == 'service' and tenant_id == conf.service_tenant_id:
                    raise common_errors.AuthenticationError('Invalid request -- only service tokens can be generated in the site-admin tenant.')
                
                try:
                    tenant_id = request.get_json().get('token_tenant_id')
                except Exception as e:
                    logger.info(f"Got exception trying to parse JSON from Tapis token request; e: {e}; type(e):{type(e)}")
                    raise common_errors.AuthenticationError('Unable to parse message payload; is it JSON?')
                # the role_name includes the tenant that the caller is trying to create the token in.
                role_name = f'{tenant_id}_token_generator'
                try:
                    # the role itself lives in the admin tenant for the site where tokens lives. the caller (which
                    # should be a service account),
                    try:
                        admin_tenant = g.tenant_id
                    except Exception as e:
                        msg = f"got exception trying to check the service token's tenant_id; exception: {e}."
                        logger.error(msg)
                        raise common_errors.AuthenticationError("Unable to validate the tenant_id on the provided JWT.")
                    logger.debug(f"calling SK to check for role: {role_name} in tenant: {admin_tenant}...")
                    users = t.sk.getUsersWithRole(tenant=admin_tenant, roleName=role_name)
                except Exception as e:
                    msg = f'Got an error calling the SK to get users with role {role_name}. Exception: {e}'
                    logger.error(msg)
                    raise common_errors.PermissionsError(
                        msg=f'Could not verify permissions with the Security Kernel; additional info: {e}')
                if g.username not in users.names:
                    logger.info(f"user {g.username} was not in role {role_name} in tenant {admin_tenant}. "
                                f"DENYING request and raising permissions error.")
                    raise common_errors.PermissionsError(msg=f'Not authorized to generate tokens in tenant {tenant_id}.')
                logger.debug(f"user {g.username} WAS fond in role {role_name} in tenant {admin_tenant}. APPROVING request.")
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
    logger.debug(f"top of check_service_password: tenant_id: {tenant_id}; username: {username}")
    # we only allow use of the "allservices_password" configuration in develop --
    if conf.use_allservices_password and "develop" in conf.primary_site_admin_tenant_base_url:
        logger.info("allowing check of the allservices_password")
        if conf.allservices_password and conf.allservices_password == password:
            logger.info("allservices_password was correct; issuing token.")
            return True
        else:
            logger.debug(f"allservices_password was incorrect; password passed: {password}; "
                         f"actual: {conf.allservices_password}")

    try:
        result = t.sk.validateServicePassword(secretType='service',
                                              secretName= 'password',
                                              tenant=tenant_id,
                                              user=username,
                                              password=password,
                                              _tapis_set_x_headers_from_service=True)
    except tapipy.errors.InvalidInputError as e:
        logger.info(f"Got InvalidInputError trying to check service password inside SK secretMap. Exception: {e}")
        raise common_errors.AuthenticationError(msg='Invalid service account/password combination. Service account may not be registered with SK.')
    except Exception as e:
        logger.debug(f"got exception from call to validateServicePassword; e: {e}; type(e): {type(e)}")
        if type(e) == common_errors.AuthenticationError:
            raise e
        logger.error(f"Got exception trying to check the service {username}'s password with SK. Exception: {e}")
        raise common_errors.AuthenticationError(msg='Tokens API got an error trying to contact SK to validate service secret.')
    if not result.isAuthorized:
        logger.debug(f"got isAuthorized==False from call to validateServicePassword. Full result: {result}")
        raise common_errors.AuthenticationError(msg='Tokens API got isAuthorized=False from SK.')


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


def check_authz_private_keypair(tenant_id):
    """
    Makes the following set of additional authorization checks:
      1). the tenant_id must be owned by the site where this Tokens API is running.
    and one of the following are true:
      2). the token's tenant_id claim matches the tenant_id being updated. OR
      3). the token's tenant_id claim is for the admin tenant for the site owning the tenant_id being updated.
    """
    # first check if the tenant_id is a tenant that this Tokens API handles
    logger.debug(f"top of check_authz_private_keypair for: {tenant_id}")
    # note that the tenant_id here could be for a tenant in status DRAFT or INACTIVE and therefore will not
    # be in the tenant cache. we have to go directly to the tenants API for to get the description for this tenant.
    request_tenant = t.tenants.get_tenant(tenant_id=tenant_id)
    site_id_for_request = request_tenant.site_id
    logger.debug(f"request_tenant: {request_tenant}; site_id_for_request: {site_id_for_request}")
    if not conf.service_site_id == site_id_for_request:
        logger.info(f"the request was for a site {site_id_for_request} that does not match the site for this Tokens"
                    f"API ({conf.service_site_id}. the request is not authorized.")
        raise common_errors.AuthenticationError(msg=f'Invalid tenant_id ({tenant_id}) provided. This tenant belongs to'
                                                    f'site {site_id_for_request} but this Tokens API serves site'
                                                    f'{conf.service_site_id}.')
    # if the tenant_id of the access token matched the tenant_id the request is trying to update, the request is
    # authorized
    if g.tenant_id == tenant_id:
        logger.debug(f"token's tenant {g.tenant_id} matched. request authorized.")
        return True
    # the rest of the checks are only for service tokens; if token was a user token, the request is not authorized:
    if not g.account_type == 'service':
        logger.info(f"the request was for a different tenant {tenant_id} than the token's tenant_id ({g.tenant_id}) and"
                    f"the token was not s service token. the request is not authorized.")
        raise common_errors.AuthenticationError(msg=f'Invalid tenant_id ({tenant_id}) provided. The token provided '
                                                    f'belongs to the {g.tenant_id} tenant but the request is trying to'
                                                    f'update the {tenant_id} tenant. Only service accounts can update'
                                                    f'other tenants.')
    # if the token tenant_id did not match the tenant_id in the request, the only way the request will be authorized is
    # if the token tenant_id is for the admin tenant of the owning site (which is the site of this Tokens API).
    # to check this, get the site associated with the token:
    token_tenant = tenants.get_tenant_config(tenant_id=g.tenant_id)
    site_id_for_token = token_tenant.site_id
    logger.debug(f"site_id_for_token: {site_id_for_token}")
    if site_id_for_request == site_id_for_token:
        logger.debug(f"token's site {site_id_for_token} matched tenant's site. request authorized.")
        return True
    logger.info(f"token site {site_id_for_token} did NOT match tenant's site ({site_id_for_request})")
    raise common_errors.AuthenticationError(msg=f'Invalid tenant_id ({tenant_id}) provided. This tenant belongs to'
                                                f'site {site_id_for_request} but the Tapis token passed in the'
                                                f'X-Tapis-Token header is for site {site_id_for_token}. Services'
                                                f'can only update tenants at their site.')


def generate_private_keypair_in_sk(tenant_id):
    """
    Generate a public/private key pair using SK for tenant_id. Returns the private key and the
    public key.
    """
    logger.debug(f"top of generate_private_keypair_in_sk for tenant_id: {tenant_id}")
    try:
        # note: writeSecret does not return the signing key generated; for that we have to
        # call readSecret
        t.sk.writeSecret(secretType='jwtsigning',
                         secretName='keys',
                         tenant=tenant_id,
                         user='tokens',
                         # these static data values instruct the SK to generate the key pair for us ---
                         data={'key': 'privateKey',
                               'value': '<generate-secret>'}
                         )
    except Exception as e:
        logger.error(f"Error from SK trying to generate key pair; exception: {e}")
    logger.info(f"new jwtsigning secret generated in SK for tenant id: {tenant_id}")
    return tenants.get_tenant_signing_keys_from_sk(t, tenant_id)
