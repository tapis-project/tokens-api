from common.auth import tenants as ts
from common.config import conf
from common import errors
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from common.logs import get_logger
logger = get_logger(__name__)


def add_tenant_private_keys():
    """
    Look up private keys associated with all tenants configured for the token service  and store them on the
    service's `tenants` singleton.
    :return:
    """
    result = []
    for tenant in ts.tenants:
        # in dev mode, the tokens service can be configured to not use the security kernel, in which case we must get
        # the private key for a "dev" tenant directly from the service configs:
        if not conf.use_sk:
            tenant['private_key'] = conf.dev_jwt_private_key
            tenant['access_token_ttl'] = conf.dev_default_access_token_ttl
            tenant['refresh_token_ttl'] = conf.dev_default_refresh_token_ttl
            result.append(tenant)
        else:
            # TODO -- get the PK from the security kernel...
            pass
    return result


tenants = add_tenant_private_keys()
logger.debug("Inside tokens.__init__, got tenants")

def get_tenant_config(tenant_id):
    """
    Return the config for a specific tenant_id from the tenants config.
    :param tenant_id:
    :return:
    """
    for tenant in tenants:
        if tenant['tenant_id'] == tenant_id:
            return tenant
    raise errors.BaseTapisError("invalid tenant id.")


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = conf.sql_db_url
db = SQLAlchemy(app)
migrate = Migrate(app, db)