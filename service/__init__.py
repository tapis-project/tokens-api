from common.auth import Tenants
from common.config import conf
from common import errors
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from common.logs import get_logger
logger = get_logger(__name__)


class TokensTenants(Tenants):

    def extend_tenant(self, t):
        """
        Add the private key and token metadata to the tenant description
        :param t: a tenant
        :return:
        """
        if not conf.use_sk:
            t.private_key = conf.dev_jwt_private_key
            t.access_token_ttl = conf.dev_default_access_token_ttl
            t.refresh_token_ttl = conf.dev_default_refresh_token_ttl
        else:
            # TODO -- get the PK from the security kernel...
            t.private_key = conf.dev_jwt_private_key
            t.access_token_ttl = conf.dev_default_access_token_ttl
            t.refresh_token_ttl = conf.dev_default_refresh_token_ttl
        return t


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

