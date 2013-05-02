import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from logbook import Logger
from functools import wraps

import maildump
import maildump.db as db


app = Flask(__name__)
app._logger = log = Logger(__name__)


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(repr(obj) + ' is not JSON serializable')


def jsonify(*args, **kwargs):
    return app.response_class(json.dumps(dict(*args, **kwargs), default=_json_default, indent=4),
                              mimetype='application/json')


def bool_arg(arg):
    return arg in ('yes', 'true', '1')


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
            response = jsonify()
            response.status_code = 204  # no content
        elif isinstance(ret, tuple):
            # code, result_dict
            response = jsonify(**ret[1])
            response.status_code = ret[0]
        else:
            response = jsonify(**ret)
        return response
    return wrapper


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/', methods=('DELETE',))
@rest
def terminate():
    log.debug('Terminate request received')
    maildump.stop()


@app.route('/messages', methods=('DELETE',))
@rest
def delete_messages():
    db.delete_messages()


@app.route('/messages', methods=('GET',))
@rest
def get_messages():
    # TODO: SSE/WebSocket support
    return {
        'messages': db.get_messages(not bool_arg(request.args.get('full')))
    }