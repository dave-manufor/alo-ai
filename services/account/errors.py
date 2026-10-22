"""The error body every Account route returns: {"error": {code, message, retryable}}, the
shape Core uses too."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AccountError(Exception):
    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable


def error_body(status: int, code: str, message: str, *, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"] if part != "body")
        message = f"{where}: {first['msg']}" if where else str(first["msg"])
        return error_body(400, "INVALID_REQUEST", message, retryable=False)

    @app.exception_handler(AccountError)
    async def account_error(request: Request, error: AccountError) -> JSONResponse:
        return error_body(error.status, error.code, error.message, retryable=error.retryable)
