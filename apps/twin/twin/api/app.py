"""The FastAPI application factory. Import-clean: nothing here reads the environment."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from twin.api.routes import router
from twin.api.schemas import MAX_BODY_BYTES, error_response
from twin.api.security import BodySizeLimitMiddleware, RequestIdMiddleware
from twin.wiring import Runtime

log = logging.getLogger("twin.api")


def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(title="Digital twin API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = runtime
    # Each add_middleware wraps the previous, so the last one added is outermost: CORS headers land on
    # every response, including the 413 the body-size middleware sends before the app sees a request.
    app.add_middleware(BodySizeLimitMiddleware, limit=MAX_BODY_BYTES)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime.settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-Id", "Retry-After"],
        allow_credentials=False,
    )
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "")} for e in exc.errors()]
        return error_response(400, "invalid_request", "The request is not valid.", detail=detail)

    @app.exception_handler(Exception)
    async def internal(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error")
        return error_response(500, "internal", "Something went wrong on our side.")

    return app
