class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def bad_request(message):
    return ApiError(400, "bad_request", message)


def not_found(message):
    return ApiError(404, "not_found", message)


def conflict(message):
    return ApiError(409, "conflict", message)
