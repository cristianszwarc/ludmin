from flask import make_response
from bson.json_util import dumps

# http://blog.alienretro.com/using-mongodb-with-flask-restful/
def output_json(obj, code, headers=None):
    """
    This is needed because we need to use a custom JSON converter
    that knows how to translate MongoDB types to JSON.
    """
    resp = make_response(dumps(obj), code)
    resp.headers.extend(headers or {})

    return resp
