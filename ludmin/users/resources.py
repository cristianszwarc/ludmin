from flask import Blueprint
from flask_restful import Api

from ..common import output_json

from .usersResource import UsersResource
from .userResource import UserResource

users_bp = Blueprint('users_api', __name__)
api = Api(users_bp)
api.representations = {'application/json': output_json}

api.add_resource(UsersResource, '')
api.add_resource(UserResource, '/<user_id>')
