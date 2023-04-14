class BaseError(Exception):
    def __init__(self, msg, code):
        self.msg = msg
        self.code = code


class BadStatusException(Exception):
    pass


class BadAPIAnswerError(Exception):
    pass


class NetworkError(Exception):
    pass


class ServerError(BaseError):
    pass


class MissingTokensError(Exception):
    pass
