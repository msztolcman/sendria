__all__ = ['json_response']

import datetime
import json
from typing import Any

import aiohttp.web
import yarl


class JSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        elif isinstance(o, yarl.URL):
            return o.human_repr()

        return json.JSONEncoder.default(self, o)


def json_response(*args, **kwargs) -> aiohttp.web.Response:
    def dumps(*a, **b) -> str:
        b['cls'] = JSONEncoder
        return json.dumps(*a, **b)
    kwargs['dumps'] = dumps
    return aiohttp.web.json_response(*args, **kwargs)
