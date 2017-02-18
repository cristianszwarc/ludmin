Users API
----------------
    Work in progress

Basic users api with JWT and per device authentication.

Use
----------------

**Public Token**

get a public JWT token for a device (if device_id is not 32 chars, a device id will be generated, this is not stored anywhere)
```
POST /tokens/public
Content-Type: application/json
{
    "device_id": char(32)
}
```

**Login**

get a logged-in JWT token
```
POST /tokens
Content-Type: application/json
Authorization: <token>
{
  "email": "some@email.net",
  "password" : "123123",
  "description": "Macbook Pro"
} 
```

**Refresh Token**

Get a new token, for logged-in tokens the process will check if the device is still logged for the user.  
```
GET /tokens/<device_id>
Content-Type: application/json
Authorization: <token>
```

**Logout**

The device will be logged-out from the user's account
```
DELETE /tokens/<device_id>
Content-Type: application/json
Authorization: <token>
```

Installation
----------------
#### Install environment ####
```
  pip3 install virtualenv
```

#### Activate environment ####
```
  virtualenv env --distribute

  source env/bin/activate
```

#### Install ####
```
  pip3 install -r requirements.txt
  
  python3 manage.py runserver
```

#### Deactivate environment ####
```
    deactivate
```
#### Switch development/testing/production modes ####
Set the environment variable LUDMIN_CONFIG to development, testing or production.

