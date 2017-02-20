from flask import Blueprint, g
from flask_restful import Api, Resource, reqparse
from flask_pymongo import ObjectId
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from ..common import output_json
from .. import mongo

users_bp = Blueprint('users_api', __name__)
api = Api(users_bp)
api.representations = {'application/json': output_json}

class UsersResource(Resource):
    def get(self):
        """ List users """

        if not g.token.has_access('master'):
            return {'error': 'Not allowed'}, 401

        # return raw list of users, just hide their password hashes
        return {'success': True, 'results': mongo.db.users.find({}, {'_id': 0, 'passwords.password': 0})}

    def post(self):
        """ Create new user"""
        if not g.token.has_access('public'):
            return { 'error': 'Not allowed' }, 401

        # validate fields
        parser = reqparse.RequestParser()
        parser.add_argument('full_name', required=True)
        parser.add_argument('email', required=True)
        parser.add_argument('password', required=True)
        parser.add_argument('password_confirmation', required=True)
        data = parser.parse_args()

        if data.get('password') != data.get('password_confirmation'):
            return { 'error': 'Password confirmation does not match' }, 400

        # we are not validating the user's email
        verified_email = False

        # check if email already in use
        if mongo.db.users.find_one({
            'emails': {
                '$elemMatch': { 'email': data.get('email') }
            }
        }):
            return { 'error': 'Email already in use' }, 400

        # create user
        current_date_time = datetime.now()
        new_user = {
            'full_name': data.get('full_name'),
            'emails': [
                {
                    'email': data.get('email'),
                    'verified': verified_email,
                    'current': True,
                    'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                }
            ],
            'passwords': [
                {
                    'current': True,
                    'password': generate_password_hash(data.get('password')),
                    'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                }
            ],
            'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
            }

        mongo.db.users.insert(new_user)
        return {'success': True}

api.add_resource(UsersResource, '')
