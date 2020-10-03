import re


class SendriaException(Exception):
    http_code = 400
    _response_code_rxp = re.compile(r'[A-Z]+[a-z0-9]+')

    def __init__(self, message=None):
        self.message = message

    def get_response_code(self):
        if hasattr(self, 'response_code'):
            return self.response_code

        cl = self.__class__.__name__[:-9]

        def repl(m):
            return m.group(0).upper() + '_'

        cl = self._response_code_rxp.sub(repl, cl)
        cl = cl.strip('_') + '_ERROR'

        return cl

    def get_message(self):
        return self.message
