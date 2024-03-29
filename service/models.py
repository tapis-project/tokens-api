import datetime
import jwt
import uuid

from tapisservice.errors import DAOError

from service import tenants, errors

# get the logger instance -
from tapisservice.logs import get_logger
logger = get_logger(__name__)


class AccessTokenData(object):
    """
    Minimal data needed to create a TapisToken object using the get_derived_values() function.
    """
    def __init__(self, jti, token_tenant_id, token_username, account_type):
        self.jti = jti
        self.token_tenant_id = token_tenant_id
        self.token_username = token_username
        self.account_type = account_type


class TapisToken(object):
    """
    Tapis tokens are not persisted to the database but are processed in similar ways to other models.
    This class collects common attributes and methods for both access and refresh tokens.
    """
    # header ----
    typ = 'JWT'
    alg = None

    # claims ----
    jti = None
    iss = None
    sub = None
    token_type = None
    tenant_id = None
    username = None
    account_type = None
    exp = None

    # non-standard claims are namespaced with the following text -
    NAMESPACE_PRETEXT = 'tapis/'

    def __init__(self, jti, iss, sub, token_type, tenant_id, username, account_type, ttl, exp, extra_claims=None, alg='RS256'):
        # header -----
        self.typ = TapisToken.typ
        self.alg = alg
        if not self.alg == 'RS256':
            raise

        # input metadata ----
        self.ttl = ttl

        # claims -----
        self.jti = jti
        self.iss = iss
        self.sub = sub
        self.token_type = token_type
        self.tenant_id = tenant_id
        self.username = username
        self.account_type = account_type
        self.exp = exp
        self.extra_claims = extra_claims

        # derived attributes
        self.expires_at = self.exp.isoformat()

        # raw jwt ----
        self.jwt = None

    def sign_token(self):
        """
        Sign the token using the private key associated with the tenant.
        :return:
        """
        tenant = tenants.get_tenant_config(self.tenant_id)
        private_key = tenant.private_key
        self.jwt = jwt.encode(self.claims_to_dict(), private_key, algorithm=self.alg)
        return self.jwt

    @classmethod
    def compute_exp(cls, ttl):
        """
        Compute the exp claim from an input ttl.
        :param ttl:
        :return:
        """
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl)

        return exp

    @classmethod
    def compute_sub(cls, tenant_id, username):
        """
        Compute the sub claim from input tenant_id and username .
        :param ttl:
        :return:
        """
        return f'{username}@{tenant_id}'

    @property
    def serialize(self):
        return {
            'jti': self.jti,
            f'{self.token_type}_token': self.jwt,
            'expires_in': self.ttl,
            'expires_at': self.expires_at
        }


class TapisAccessToken(TapisToken):
    """
    Adds attributes and methods specific to access tokens.
    """
    delegation = None
    delegation_sub = None

    # these are the standard Tapis access token claims and cannot appear in the extra_claims parameter -
    standard_tapis_access_claims = ('jti', 'iss', 'sub', 'tenant', 'target_site', 'username', 'account_type', 'exp')

    def __init__(self, jti, iss, sub, tenant_id, username, account_type, ttl, exp, delegation, delegation_sub=None,
                 target_site_id=None, extra_claims=None):
        super().__init__(jti, iss, sub, 'access', tenant_id, username, account_type, ttl, exp, extra_claims)
        self.delegation = delegation
        self.delegation_sub = delegation_sub
        self.target_site_id = target_site_id
        self.extra_claims = extra_claims


    def claims_to_dict(self):
        """
        Returns a dictionary of claims.
        :return:
        """
        d = {
            'jti': self.jti,
            'iss': self.iss,
            'sub': self.sub,
            f'{TapisToken.NAMESPACE_PRETEXT}tenant_id': self.tenant_id,
            f'{TapisToken.NAMESPACE_PRETEXT}token_type': self.token_type,
            f'{TapisToken.NAMESPACE_PRETEXT}delegation': self.delegation,
            f'{TapisToken.NAMESPACE_PRETEXT}delegation_sub': self.delegation_sub,
            f'{TapisToken.NAMESPACE_PRETEXT}username': self.username,
            f'{TapisToken.NAMESPACE_PRETEXT}account_type': self.account_type,
            'exp': self.exp,
        }
        if self.target_site_id:
            d[f'{TapisToken.NAMESPACE_PRETEXT}target_site'] = self.target_site_id
        if self.extra_claims:
            d.update(self.extra_claims)
        return d


    @classmethod
    def get_derived_values(cls, data):
        """
        Computes derived values for the access token from input and defaults.
        :param data:
        :return: dict (result)
        """
        # convert required fields to their data model attributes -
        try:
            result = {'tenant_id': data.token_tenant_id,
                      'username': data.token_username,
                      'account_type': data.account_type,
                      }
        except KeyError as e:
            logger.error(f"Missing required token attribute; KeyError: {e}")
            raise DAOError("Missing required token attribute.")

        # service tokens must also have a target_site claim:
        if result['account_type'] == 'service':
            if hasattr(data, 'target_site_id'):
                result['target_site_id'] = data.target_site_id
            else:
                raise errors.InvalidTokenClaimsError("The target_site_id claim is required for 'service' tokens.")

        # generate a jti
        result['jti'] = str(uuid.uuid4())

        # compute the subject from the parts
        result['sub'] = TapisToken.compute_sub(result['tenant_id'], result['username'])
        tenant = tenants.get_tenant_config(result['tenant_id'])
        # derive the issuer from the associated config for the tenant.
        result['iss'] = tenant.token_service

        # compute optional fields -
        access_token_ttl = getattr(data, 'access_token_ttl', None)
        if not access_token_ttl or access_token_ttl <= 0:
            access_token_ttl = tenant.access_token_ttl
        result['ttl'] = access_token_ttl
        result['exp'] = TapisToken.compute_exp(access_token_ttl)

        delegation = getattr(data, 'delegation_token', False)
        result['delegation'] = delegation
        # when creating a delegation token, the components needed to create the delegation sub are required:
        if delegation:
            try:
                delegation_tenant_id = data.delegation_sub_tenant_id
                delegation_username = data.delegation_sub_username
            except (AttributeError, KeyError) as e:
                logger.error(f"Missing required delegation token attribute; KeyError: {e}")
                raise DAOError("Missing required delegation token attribute; both delegation_sub_tenant_id and "
                               "delegation_sub_username are required when generating a delegation token.")
            result['delegation_sub'] = TapisToken.compute_sub(delegation_tenant_id, delegation_username)
        if hasattr(data, 'claims'):
            # result.update(data.claims)
            result['extra_claims'] = data.claims
        return result


class TapisRefreshToken(TapisToken):
    """
    Adds attributes and methods specific to refresh tokens.
    """
    access_token = None

    def __init__(self, jti, iss, sub, tenant_id, username, account_type, ttl, exp, access_token):
        super().__init__(jti, iss, sub, 'refresh', tenant_id, username, account_type, ttl, exp, None)
        self.access_token = access_token

    @classmethod
    def get_derived_values(cls, data):
        result = data
        result['jti'] = str(uuid.uuid4())
        refresh_token_ttl = result.pop('refresh_token_ttl', None)
        if not refresh_token_ttl or refresh_token_ttl <= 0:
            tenant = tenants.get_tenant_config(result['tenant_id'])
            refresh_token_ttl = tenant.refresh_token_ttl
        result['ttl'] = refresh_token_ttl
        result['exp'] = TapisToken.compute_exp(refresh_token_ttl)
        return result

    def claims_to_dict(self):
        """
        Returns a dictionary of claims.
        :return:
        """
        d = {
            'jti': self.jti,
            'iss': self.iss,
            'sub': self.sub,
            # we store the initial ttl on a refresh token because, when using the refresh operation, a new
            # refresh token with the same ttl will be created.
            f'{TapisToken.NAMESPACE_PRETEXT}initial_ttl': self.ttl,
            f'{TapisToken.NAMESPACE_PRETEXT}tenant_id': self.tenant_id,
            f'{TapisToken.NAMESPACE_PRETEXT}token_type': self.token_type,
            # NOTE: we intentionally do not include these claims, as the refresh token should not be
            #       honored by services as an access token.
            # 'username': self.username,
            # 'account_type': self.account_type,
            'exp': self.exp,
            f'{TapisToken.NAMESPACE_PRETEXT}access_token': self.access_token
        }
        return d
