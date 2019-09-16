from flask_migrate import Migrate

from common.utils import TapisApi, handle_error, flask_errors_dict

from service.controllers import TokensResource
from service.models import db, app

# db and migrations ----
db.init_app(app)
migrate = Migrate(app, db)

# flask restful API object ----
api = TapisApi(app, errors=flask_errors_dict)

# Set up error handling
api.handle_error = handle_error
api.handle_exception = handle_error
api.handle_user_exception = handle_error

# Add resources
api.add_resource(TokensResource, '/tokens')
