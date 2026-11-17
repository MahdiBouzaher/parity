import platform
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, datasets, db, runs, verify
from .errors import ApiError


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="Parity", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def error_response(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return error_response(400, "bad_request", "The request is missing a field or has a wrong value.")


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return error_response(404, "not_found", "This address does not exist.")
    if exc.status_code == 405:
        return error_response(405, "bad_request", "This method is not allowed here.")
    return error_response(exc.status_code, "bad_request", "The request could not be handled.")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    return error_response(500, "run_failed", "The server hit an internal error.")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "translation_model": {
            "configured": config.model_configured(),
            "name": config.model_name(),
        },
        "python": platform.python_version(),
        "pandas": pd.__version__,
    }


app.include_router(datasets.router)
app.include_router(datasets.samples_router)
app.include_router(runs.router)
app.include_router(verify.router)
