import os
from flask import Flask, jsonify, request, g
from flask_pymongo import PyMongo

from config import config
from .tokens.token import Token

# Flask extensions
mongo = PyMongo()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('LUDMIN_CONFIG', 'development')
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize flask extensions
    mongo.init_app(app)

    # Register API routes
    from .tokens.resources import tokens_bp
    app.register_blueprint(tokens_bp, url_prefix='/tokens')

    from .users.resources import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')

    # custom handlers
    @app.errorhandler(500)
    def internal_server_error(error):
        """ When not in debug mode, handle any 500 """
        return jsonify({'error': 'unexpected'}), 500

    # handle not found routes
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'not found'}), 404

    @app.before_request
    def global_validations():
        # check the body is not empty when not using GET/DELETE
        if request.method != 'GET' and request.method != 'DELETE' and not request.get_json():
            return jsonify({"error": "Invalid request."})

        # store the token for this request (when available)
        g.token = Token(app.config, request.headers.get('Authorization'))

        # validate the token for any route that is not requesting a new token
        rule = request.url_rule
        if rule and '/token' not in rule.rule:
            try:
                g.token.decode_token_or_fail()
            except Exception as e:
                # immediate fail for any issue with the token
                return jsonify({'error': str(e)}), 500

    return app
