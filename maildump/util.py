import json
import pkg_resources
from datetime import datetime
from email.header import decode_header as _decode_header
from email.utils import getaddresses
from functools import wraps

from pytz import utc
from flask import current_app


def _json_default(obj):
    if isinstance(obj, datetime):
        return utc.localize(obj).isoformat()
    raise TypeError(repr(obj) + ' is not JSON serializable')


def json_dumps(obj):
    return json.dumps(obj, default=_json_default, indent=4)


def jsonify(*args, **kwargs):
    return current_app.response_class(json_dumps(dict(*args, **kwargs)), mimetype='application/json')


def bool_arg(arg):
    return arg in ('yes', 'true', '1')


def decode_header(value):
    if not value:
        return ''
    headers = [decoded.encode(charset or 'utf-8') for decoded, charset in _decode_header(value)]
    return (b''.join(headers)).decode()


def split_addresses(value):
    return [('{0} <{1}>'.format(name, addr) if name else addr)
            for name, addr in getaddresses([value])]


def rest(f):
    """Decorator for simple REST endpoints.

    Functions must return one of these values:
    - a dict to jsonify
    - nothing for an empty 204 response
    - a tuple containing a status code and a dict to jsonify
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        ret = f(*args, **kwargs)
        if ret is None:
            response = '', 204
        elif isinstance(ret, current_app.response_class):
            response = ret
        elif isinstance(ret, tuple):
            # code, result_dict|msg_string
            if isinstance(ret[1], basestring):
                response = jsonify(msg=ret[1])
            else:
                response = jsonify(**ret[1])
            response.status_code = ret[0]
        else:
            response = jsonify(**ret)
        return response

    return wrapper


def get_version():
    try:
        return 'v' + pkg_resources.get_distribution('maildump').version
    except pkg_resources.DistributionNotFound:
        return 'dev'
