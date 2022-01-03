from tapisservice.tapisflask.utils import TapisApi, handle_error, flask_errors_dict
from tapisservice.tapisflask.resources import HelloResource, ReadyResource

from service.auth import authn_and_authz
from service.controllers import TokensResource, SigningKeysResource

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

# Health-checks
api.add_resource(ReadyResource, '/v3/tokens/ready')
api.add_resource(HelloResource, '/v3/tokens/hello')

api.add_resource(TokensResource, '/v3/tokens')
api.add_resource(SigningKeysResource, '/v3/tokens/keys')
