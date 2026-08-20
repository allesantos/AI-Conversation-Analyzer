class AppError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class BadRequestError(AppError):
    status_code = 400


class PayloadTooLargeError(AppError):
    status_code = 413


class ProcessingError(AppError):
    status_code = 202

    def __init__(self, message: str, *, processing_status: str = "PROCESSING") -> None:
        self.processing_status = processing_status
        super().__init__(message)
