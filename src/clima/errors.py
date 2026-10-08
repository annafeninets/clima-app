"""Application errors translated to stable HTTP responses."""


class AppError(Exception):
    status_code = 400
    code = "application_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AuthError(AppError):
    status_code = 401
    code = "authentication_error"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AccessDeniedError(AppError):
    status_code = 403
    code = "access_denied"


class NotEnoughItemsError(AppError):
    status_code = 409
    code = "not_enough_items"

    def __init__(
        self, message: str, missing: list[str] | None = None,
        have: dict[str, int] | None = None,
    ):
        super().__init__(message)
        self.missing = missing
        self.have = have
        if missing is not None:
            self.code = "insufficient_wardrobe"


class BadCombinationError(AppError):
    status_code = 409
    code = "bad_combination"


class AlreadyFavoriteError(AppError):
    status_code = 409
    code = "already_favorite"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
