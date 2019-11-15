from common.utils import TapisApi, handle_error, flask_errors_dict

from service.auth import authn_and_authz
from service.controllers import TokensResource

from service import app, db

# authentication and authorization ---
@app.before_request
def authnz_for_authenticator():
    authn_and_authz()

# flask restful API object ----
api = TapisApi(app, errors=flask_errors_dict)

# Set up error handling
api.handle_error = handle_error
api.handle_exception = handle_error
api.handle_user_exception = handle_error

# Add resources
api.add_resource(TokensResource, '/tokens')
