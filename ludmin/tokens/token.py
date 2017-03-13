import jwt
from datetime import datetime, timedelta, timezone


class Token:
    """Token functions"""
    def __init__(self, config, token):
        if token:
            token = token.replace("Bearer", "").strip()
        self.token = token              # store the token
        self.config = config            # store the token
        self.decoded = self.decode()    # decode it as soon it arrives

        if not self.config['SECRET_KEY']:
            self.config['SECRET_KEY'] = 'notsosecret1234567890987654321'
            print('Warning: SECRET_KEY not in config file!!!')

        if not self.config['TOKEN_TIMEOUT']:
            self.config['TOKEN_TIMEOUT'] = 300
            print('Warning: TOKEN_TIMEOUT not in config file!!!')

    # decode the token or throw exception
    def decode_token_or_fail(self, verify_exp=True):
        return jwt.decode(
                self.token,
                self.config['SECRET_KEY'],
                options={'verify_exp': verify_exp},
                algorithms=['HS256']
            )

    # decode the token or return an empty dictionary
    def decode(self):
        try:
            return self.decode_token_or_fail()
        except Exception:
            return {}

    # check if the area is allowed in this token
    def has_access(self, area):
        try:
            if area in self.decoded.get('allowed'):
                return True
        except Exception:
            return False

        return False

    def generate(self, payload):
        # append default expiration time
        payload['exp'] = datetime.now(timezone.utc) + timedelta(seconds=self.config['TOKEN_TIMEOUT'])
        return jwt.encode(payload, self.config['SECRET_KEY'], algorithm='HS256')

    def generate_public(self, device_id, allowed):
        return self.generate({
                'device_id': device_id,
                'type': 'public',
                'allowed': allowed,
            })

    def generate_logged(self, user_for_device, device_id, allowed, rev):
        return self.generate({
            'device_id': device_id,
            'type': 'logged',
            '_id': str(user_for_device.get('_id')),
            'rev': rev,
            'full_name': user_for_device.get('full_name'),
            'allowed': allowed
        })
