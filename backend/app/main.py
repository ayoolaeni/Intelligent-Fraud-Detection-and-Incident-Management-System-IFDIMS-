"""FastAPI app: routers, CORS, startup (load model, start SLA scheduler)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import admin, alerts, auth, cases, dashboard, notifications, reports, transactions
from app.config import get_settings
from app.db import SessionLocal
from app.services import sla_service
from app.services.model_registry import model_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ifdims")

scheduler = BackgroundScheduler()


def _check_active_model_job() -> None:
    db = SessionLocal()
    try:
        model_registry.refresh_if_changed(db)
    except Exception:
        logger.exception("Active-model refresh check failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_production()

    db = SessionLocal()
    try:
        model_registry.load_active_from_db(db)
        if model_registry.loaded:
            logger.info("Loaded active model %s", model_registry.loaded.version)
        else:
            logger.warning("No active model found at startup; /transactions/score will return 503")
    finally:
        db.close()

    scheduler.add_job(sla_service.run_sla_check, "interval", seconds=60, id="sla_check")
    # Runs in every worker process independently (no advisory lock needed:
    # each worker only ever touches its own in-memory model_registry).
    scheduler.add_job(_check_active_model_job, "interval", seconds=10, id="model_check")
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="IFDIMS API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "detail" in exc.detail and "code" in exc.detail:
        content = exc.detail
    else:
        content = {"detail": str(exc.detail), "code": "ERROR"}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # exc.errors() may embed the raw exception object in ctx for
    # "value_error" (e.g. a validator that raises ValueError), which is not
    # JSON-serializable, so only pass through the plain-text fields.
    safe_errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "code": "VALIDATION_ERROR", "errors": safe_errors},
    )


app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    db_status = "ok"
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        db_status = "error"

    loaded = model_registry.loaded
    return {
        "status": "ok",
        "db": db_status,
        "model_loaded": loaded is not None,
        "model_version": loaded.version if loaded else None,
    }
