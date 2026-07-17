class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} '{id}' not found.", status_code=404)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class CloudinaryError(AppError):
    def __init__(self, message: str):
        super().__init__(f"Cloudinary error: {message}", status_code=502)


class CacheError(AppError):
    def __init__(self, message: str):
        super().__init__(f"Cache error: {message}", status_code=500)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)