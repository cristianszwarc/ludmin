from flask import Blueprint, g
from flask_restful import Api, Resource, reqparse
from flask_pymongo import ObjectId
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
#from flask_restful.utils import cors
import uuid
import random

from .. import mongo

tokens_bp = Blueprint('tokens_api', __name__)
api = Api(tokens_bp)
#api.decorators = [cors.crossdomain(origin='*', headers=['accept', 'Content-Type', 'Authorization'])]

class PublicTokensResource(Resource):
    def options(self):
        pass

    def post(self):
        """ Public token for a device, when not device id provided, generate a random one """

        parser = reqparse.RequestParser()
        parser.add_argument('device_id', required=True)
        data = parser.parse_args()
        device_id = data.get('device_id')

        # use given id, else generate one
        if not device_id or len(device_id) != 32:
            device_id = uuid.uuid4().hex

        public_token = g.token.generate_public(device_id, ['public'])
        return {'success': True, 'device_id': device_id, 'token': public_token.decode('utf-8')}


class TokensResource(Resource):
    def options(self, device_id=None):
        pass
    
    def get(self, device_id):
        """Refresh a token"""
        new_token = False        # new generated token
        token_type = False       # hint to show what type of token is created

        # check if we have a current token. Expiration is not relevant, the database
        # will dictate if the device is really logged-in or a public token will be issued
        try:
            # the decoded token may be expired and not available, decode it ignoring the expiration
            token_to_refresh = g.token.decode_token_or_fail(verify_exp=False)

            # only accept the token's user_id if the device id from the url matches the one in the token
            if device_id == token_to_refresh.get('device_id'):
                user_id = token_to_refresh.get('_id')
                token_rev = token_to_refresh.get('rev')
            else:
                return {'error': 'Inconsistent device id'}, 500

        except Exception:
            # we require a token to be refreshed, even a public one
            return {'error': 'Invalid Token'}, 500

        # random version for this token
        rev = random.randint(0, 9999)

        # if we have a token owner and a device, check if the device still attached to the user
        # we are going to have an user_id only if a logged-in token was provided (despite expired)
        if user_id and device_id:
            user_for_device = mongo.db.users.find_one({
                '_id': ObjectId(user_id),
                'devices': {
                    '$elemMatch': {
                        'device_id': device_id,
                        'rev': token_rev
                    }
                }})

            # if this device still attached to the user, issue new token
            if user_for_device:
                # update device's lastUsed and rev
                current_date_time = datetime.now(timezone.utc)
                mongo.db.users.update({
                    '_id': user_for_device.get('_id'), 'devices.device_id': device_id},
                    {'$set': {
                        'devices.$.lastUsed': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'devices.$.rev': rev,
                    }},
                    True
                )

                # issue fresh token
                token_type = 'Refresh'
                new_token = g.token.generate_logged(user_for_device, device_id, ['basics', 'master'], rev)

        # if a new token was not created, issue a new public token by default
        if not new_token:
            token_type = 'Public'
            new_token = g.token.generate_public(device_id, ['public'])

        return {'success': True, 'token': new_token.decode('utf-8'), 'type': token_type}

    def post(self):
        """Login, generates a new token"""
        if not g.token.has_access('public') and not g.token.has_access('basics'):
            return {'error': 'Not allowed'}, 401

        device_id = g.token.decoded.get('device_id')

        # validate fields
        parser = reqparse.RequestParser()
        parser.add_argument('email', required=True)
        parser.add_argument('password', required=True)
        parser.add_argument('description', required=True)
        data = parser.parse_args()

        # load the user by email
        user = mongo.db.users.find_one({
                'emails': {
                    '$elemMatch': {
                        'email': data.get('email'),
                        'current': True
                    }
                }
            })

        if not user:
            return {'error': 'Incorrect user or password'}, 400

        current_password = next((item for item in user.get('passwords') if item.get('current') is True), None)

        # check if the given password is correct
        if not current_password or not check_password_hash(current_password.get('password'), data.get('password')):
            return {'error': 'Incorrect user or password'}, 400

        # random version for this token
        rev = random.randint(0, 9999)
        user_devices = user.get('devices') or []        # get current user's devices
        if not any(device.get('device_id') == device_id for device in user_devices):
            # the device is not included for this user
            current_date_time = datetime.now(timezone.utc)
            user_devices.append({
                'device_id': device_id,
                'rev': rev,
                'lastUsed': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                'description': data.get('description')
            })
            user.update({'devices': user_devices})
            mongo.db.users.save(user)
        else:
            # device exist for this user, need to update rev and lastUsed
            current_date_time = datetime.now(timezone.utc)
            mongo.db.users.update({
                '_id': user.get('_id'), 'devices.device_id': device_id},
                {'$set': {
                    'devices.$.lastUsed': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'devices.$.rev': rev,
                }},
                True
            )

        # generate logged-in JWT
        encoded = g.token.generate_logged(user, device_id, ['basics', 'master'], rev)

        # return the logged-in token
        return {
                   'success': True,
                   'token': encoded.decode('utf-8'),
                   'type': 'Login'
               }, 201

    def delete(self, device_id):
        """Remove the token (logout)"""

        try:
            # the decoded token may be expired, decode it ignoring the expiration
            # it's ok to logout with an expired token when the device matches the token.device_id
            token_to_refresh = g.token.decode_token_or_fail(verify_exp=False)

            # the device_id is not from the current token, validate expiration
            # the user is allowed to logout other devices
            if device_id != token_to_refresh.get('device_id'):
                token_to_refresh = g.token.decode_token_or_fail()

        except Exception:
            return {'error': 'Invalid Token'}, 500

        # check that the device_id exist and belongs to the current user
        user_for_device = mongo.db.users.find_one({
            '_id': ObjectId(token_to_refresh.get('_id')),
            'devices': {
                '$elemMatch': {'device_id': device_id}
            }})

        # if the device is attached to the user, remove it
        if user_for_device:
            mongo.db.users.update(
                {'_id': user_for_device.get('_id')},
                {'$pull': {"devices": {'device_id': device_id}}},
                True
            )
            return {'success': True}

        return {'error': 'Device not linked to user.'}

api.add_resource(TokensResource, '', '/<string:device_id>')
api.add_resource(PublicTokensResource, '', '/public')
