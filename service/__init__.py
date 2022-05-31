from tapisservice.tenants import TenantCache
from tapisservice.config import conf
from tapisservice import errors
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from tapisservice.logs import get_logger
logger = get_logger(__name__)


class TokensTenants(TenantCache):

    def extend_tenant(self, t):
        """
        Add the private key and token metadata to the tenant description
        :param t: a tenant
        :return:
        """
        # if conf.use_sk is true, we need to get the PKs from the security kernel, but in order to do that we must have
        # a working tapipy client, which isn't created until the auth module initializes. However,
        # in order to create the tapipy client, we need a private key for at least the site admin tenant so
        # that we can sign a service token for it.
        # Therefore, tokens API requires the private key for its tenant to be injected into the container,
        # and here we set that private key.

        # the name of the attribute that has the private key for the site admin tenant is: site_admin_privatekey        
        logger.debug(f"top of extend_tenant for tenant: {t.tenant_id}")
        tenant_id = t.tenant_id
        if not tenant_id in conf.tenants:
            logger.debug(f"skipping tenant_id: {tenant_id} as it is not in the list of tenants.")
            return t
        try:
            t.private_key = conf.site_admin_privatekey
        except Exception as e:
            msg = f"Tokens could not get the private key attribute from the conf object. "\
                     "It was looking for an attribute called site_admin_privatekey. Here is the conf object: {conf}."
            logger.error(msg)
            raise e
        t.access_token_ttl = conf.dev_default_access_token_ttl
        t.refresh_token_ttl = conf.dev_default_refresh_token_ttl
        return t

    def get_tenant_signing_keys_from_sk(self, t, tenant_id):
        """
        Retrieve the signing key for a tenant from the SK. This is used at service start up from within
        the auth.py module, once the tapipy client (t) is created.
        """
        logger.debug(f"top of get_tenant_signing_keys_from_sk for tenant_id: {tenant_id}")
        try:
            result = t.sk.readSecret(secretType='jwtsigning',
                                     secretName='keys',
                                     tenant=tenant_id,
                                     user='tokens',
                                     _tapis_set_x_headers_from_service=True)
        except Exception as e:
            logger.error(f"Error from SK trying to read tenant signing key for tenant {tenant_id}; exception: {e}")
            raise e
        logger.debug(f"returning signing key for tenant_id: {tenant_id}")
        return result.secretMap.privateKey, result.secretMap.publicKey


# singleton with all tenants data and reload capabilities, etc.
tenants = TokensTenants()

logger.debug("Inside tokens.__init__, got tenants")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = conf.sql_db_url
db = SQLAlchemy(app)
migrate = Migrate(app, db)


def create_initial_roles():
    """
    Tokens API depends on roles defined in the SK to check authorization
    """
    # todo --
    pass

