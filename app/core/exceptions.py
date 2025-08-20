# app/core/exceptions.py
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY


async def validation_exception_handler(request, exc: RequestValidationError):
    print("VALIDATION ERR:", exc.errors())
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                        content={"detail": exc.errors()})
