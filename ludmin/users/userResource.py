from flask_restful import Resource, reqparse
from flask_pymongo import ObjectId
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from flask import g
from .. import mongo


class UserResource(Resource):
    def get(self, user_id):
        """ User profile """

        if not g.token.has_access('basics'):
            return {'error': 'Not allowed'}, 401

        session_user_id = g.token.decoded.get('_id')

        # alias for the current user
        if user_id == 'me':
            user_id = session_user_id

        # try to load the user (without the password hashes)
        try:
            user = mongo.db.users.find_one({
                    '_id': ObjectId(user_id)
                }, {'_id': 0, 'passwords.password': 0})
        except Exception:
            return {'error': 'Error loading user'}, 404

        if not user:
            return {'error': 'Not found'}, 404

        # public profile when getting someone else profile and not master
        if user_id != session_user_id and not g.token.has_access('master'):
            return {
                'success': True,
                'profile': {
                    'full_name': user.get('full_name')
                }
            }

        # load full profile for self profile or master users
        current_email = next((item for item in user.get('emails') if item.get('current') is True), None)

        return {
            'success': True,
            'profile': {
                'full_name': user.get('full_name'),
                'current_email': current_email.get('email'),
                'devices': user.get('devices'),
                'emails': user.get('emails'),
                'passwords': user.get('passwords') if g.token.has_access('master') else None
            }
        }

    def put(self, user_id):
        """ Update user details """

        if not g.token.has_access('basics'):
            return {'error': 'Not allowed'}, 401

        # validate fields
        parser = reqparse.RequestParser()
        parser.add_argument('full_name')
        parser.add_argument('email')
        parser.add_argument('password')
        parser.add_argument('password_confirmation')
        parser.add_argument('current_password')
        data = parser.parse_args()

        session_user_id = g.token.decoded.get('_id')

        # alias for the current user
        if user_id == 'me':
            user_id = session_user_id

        # not allow update other users unless is master
        if user_id != session_user_id and not g.token.has_access('master'):
            return {'error': 'Not allowed'}, 401

        # load user (even with hashes, must load the full object to perform a full update later)
        try:
            user = mongo.db.users.find_one({
                    '_id': ObjectId(user_id)
                })
        except Exception:
            return {'error': 'Error loading user'}, 404

        # if the current password is given, validate it (required later on for sensitive data changes)
        verified_pass = False
        if data.get('current_password'):
            user_passwords = user.get('passwords') or []
            for pass_to_check in user_passwords:
                found = check_password_hash(pass_to_check.get('password'), data.get('current_password'))\
                        and pass_to_check.get('current')
                if found:
                    verified_pass = True
                    break

        # start partial updates
        current_date_time = datetime.now()
        if data.get('full_name'):
            user.update({
                    'full_name': data.get('full_name')
                })

        # email update
        if data.get('email'):
            # email change requires current password
            if not verified_pass:
                return {'error': 'Unable to verify current password.'}, 401

            # check email is already registered
            email_exist_details = mongo.db.users.find_one({
                'emails': {
                    '$elemMatch': {'email': data.get('email')}
                }
            })

            # we can not use the email if registered on other user
            if email_exist_details and email_exist_details.get('_id') != user.get('_id'):
                return {'error': 'Email already in use by other user.'}, 400

            # append the new email if not already included on this user
            user_emails = user.get('emails') or []
            if not any(email.get('email') == data.get('email') for email in user_emails):
                user_emails.append({
                    'email': data.get('email'),
                    'verified': False,
                    'current': True,
                    'insertedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                })

            # mark the new email as the current one and un-mark the previous one
            for email_to_unflag in user_emails:
                is_current = email_to_unflag.get('email') == data.get('email')

                # was already used before, set an updatedAt
                if is_current != email_to_unflag.get('current'):
                    email_to_unflag.update({
                        'updatedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                    })

                # mark current or not
                email_to_unflag.update({
                        'current': is_current
                    })

            user.update({'emails': user_emails})

        # password is being updated
        if data.get('password'):
            # email change requires current password
            if not verified_pass:
                return {'error': 'Unable to verify current password.'}, 401

            # validate the password
            if data.get('password') != data.get('password_confirmation'):
                return {'error': 'Password confirmation does not match.'}, 400

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
            for passToUnflag in user_passwords:
                is_current = check_password_hash(passToUnflag.get('password'), data.get('password'))

                # is not the current but was already used, update hash
                if is_current != passToUnflag.get('current'):
                    passToUnflag.update({
                            'updatedAt': current_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                        })

                # mark current or not
                passToUnflag.update({
                        'current': is_current
                    })

            user.update({'passwords': user_passwords})

        # send the changes to the db
        mongo.db.users.save(user)
        return {'success': True}
