from flask_restful import Resource, reqparse
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import random

from flask import g
from .. import mongo


class ResetPasswordResource(Resource):
    def options(self):
        pass

    def get(self):
        """List current reset requests, undocumented."""

        if not g.token.has_access('master'):
            return {'error': 'Not allowed'}, 401

        return {'success': True, 'results': mongo.db.reset_requests.find({}, {'_id': 0})}

    def post(self):
        """Generate a reset password code"""
        if not g.token.has_access('public'):
            return {'error': 'Not allowed'}, 401

        # validate fields
        parser = reqparse.RequestParser()
        parser.add_argument('email', required=True)
        data = parser.parse_args()

        # the email must exist and must be the current one
        user_for_email = mongo.db.users.find_one({
            'emails': {
                '$elemMatch': {
                    'email': data.get('email'),
                    'current': True
                }
            }
        })

        # we can not use the email if registered on other user
        if not user_for_email:
            return {'error': 'Email not registered for any user.'}, 400

        # generate a reset password record
        current_date_time = datetime.now()
        generated_code = random.randint(1000, 9999)
        new_reset = {
            'email': data.get('email'),
            'sent': False,
            'enabled': True,
            'failures': 0,
            'code': str(generated_code),
            'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        mongo.db.reset_requests.insert(new_reset)
        return {'success': True}

    def put(self):
        """Set a new password given a reset code"""
        if not g.token.has_access('public'):
            return {'error': 'Not allowed'}, 401

        current_date_time = datetime.now()

        # validate fields
        parser = reqparse.RequestParser()
        parser.add_argument('email', required=True)
        parser.add_argument('code', required=True)
        parser.add_argument('password', required=True)
        parser.add_argument('password_confirmation', required=True)
        data = parser.parse_args()

        # load the reset record
        reset_record = mongo.db.reset_requests.find_one({
            'email': data.get('email'),
            'enabled': True,
            'failures': {"$lt": 4}
        })
        if not reset_record:
            return {'error': 'No reset request found for this email.'}, 400

        # load the user for the provided email
        user = mongo.db.users.find_one({
            'emails': {
                '$elemMatch': {
                    'email': data.get('email'),
                    'current': True
                }
            }
        })
        if not user:
            return {'error': 'Unable to find active email.'}, 400

        # validate the new password
        if data.get('password') != data.get('password_confirmation'):
            return {'error': 'Password confirmation does not match.'}, 400

        # if the code is incorrect, update failures count
        if reset_record.get('code') != data.get('code'):
            reset_record.update({
                'failures': reset_record.get('failures') + 1,
                'updatedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S')
            })
            mongo.db.reset_requests.save(reset_record)
            return {'error': 'Invalid code, try again.'}, 400

        # everything is valid, invalidate the reset record
        reset_record.update({
            'enabled': False,
            'updatedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S')
        })
        mongo.db.registrations.save(reset_record)

        # append new password if not already used before
        user_passwords = user.get('passwords') or []
        if not any(check_password_hash(currentPassword.get('password'), data.get('password'))
                   for currentPassword in user_passwords
                   ):
            user_passwords.append({
                'current': True,
                'password': generate_password_hash(data.get('password')),
                'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
            })

        # mark the current password
        for pass_to_unflag in user_passwords:
            is_current = check_password_hash(pass_to_unflag.get('password'), data.get('password'))

            # is not the current but was already used, update hash
            if is_current != pass_to_unflag.get('current'):
                pass_to_unflag.update({
                    'updatedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                })

            # mark current or not
            pass_to_unflag.update({
                'current': is_current
            })

        user.update({'passwords': user_passwords})

        # send the changes to the db
        mongo.db.users.save(user)
        return {'success': True}
