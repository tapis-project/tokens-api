import datetime
import jwt
from common.errors import DAOError

from service import tenants, get_tenant_config, db

# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)


class TapisToken(object):
    """
    Tapis tokens are not persisted to the database but are processed in similar ways to other models.
    This class collects common attributes and methods for both access and refresh tokens.
    """
    # header ----
    typ = 'JWT'
    alg = None

    # claims ----
    iss = None
    sub = None
    token_type = None
    tenant_id = None
    username = None
    account_type = None
    exp = None

    # non-standard claims are namespaced with the following text -
    NAMESPACE_PRETEXT = 'tapis/'

    def __init__(self, iss, sub, token_type, tenant_id, username, account_type, ttl, exp, extra_claims=None, alg='RS256'):
        # header -----
        self.typ = TapisToken.typ
        self.alg = alg
        if not self.alg == 'RS256':
            raise

        # input metadata ----
        self.ttl = ttl

        # claims -----
        self.iss = iss
        self.sub = sub
        self.token_type = token_type
        self.tenant_id = tenant_id
        self.username = username
        self.account_type = account_type
        self.exp = exp
        self.extra_claims = extra_claims

        # derived attributes
        self.expires_at = str(self.exp)

        # raw jwt ----
        self.jwt = None

    def sign_token(self):
        """
        Sign the token using the private key associated with the tenant.
        :return:
        """
        tenant = get_tenant_config(self.tenant_id)
        private_key = tenant['private_key']
        self.jwt = jwt.encode(self.claims_to_dict(), private_key, algorithm=self.alg)
        return self.jwt

    @classmethod
    def compute_exp(cls, ttl):
        """
        Compute the exp claim from an input ttl.
        :param ttl:
        :return:
        """
        return datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)

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
            f'{self.token_type}_token': self.jwt.decode('utf-8'),
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
    standard_tapis_access_claims = ('iss', 'sub', 'tenant', 'username', 'account_type', 'exp')

    def __init__(self, iss, sub, tenant_id, username, account_type, ttl, exp, delegation, delegation_sub=None,
                 extra_claims=None):
        super().__init__(iss, sub, 'access', tenant_id, username, account_type, ttl, exp, extra_claims)
        self.extra_claims = extra_claims
        self.delegation = delegation
        self.delegation_sub = delegation_sub

    def claims_to_dict(self):
        """
        Returns a dictionary of claims.
        :return:
        """
        d = {
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

        # compute the subject from the parts
        result['sub'] = TapisToken.compute_sub(result['tenant_id'], result['username'])
        tenant = get_tenant_config(result['tenant_id'])
        # derive the issuer from the associated config for the tenant.
        result['iss'] = tenant['iss']

        # compute optional fields -
        access_token_ttl = getattr(data, 'access_token_ttl', None)
        if not access_token_ttl:
            access_token_ttl = tenant['access_token_ttl']
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

    def __init__(self, iss, sub, tenant_id, username, account_type, ttl, exp, access_token):
        super().__init__(iss, sub, 'refresh', tenant_id, username, account_type, ttl, exp, None)
        self.access_token = access_token


    @classmethod
    def get_derived_values(cls, data):
        result = data
        refresh_token_ttl = result.pop('refresh_token_ttl', None)
        if not refresh_token_ttl:
            tenant = get_tenant_config(result['tenant_id'])
            refresh_token_ttl = tenant['refresh_token_ttl']
        result['ttl'] = refresh_token_ttl
        result['exp'] = TapisToken.compute_exp(refresh_token_ttl)
        return result

    def claims_to_dict(self):
        """
        Returns a dictionary of claims.
        :return:
        """
        d = {
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
