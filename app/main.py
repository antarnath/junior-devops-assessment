"""Apex Operations API.

A small FastAPI service that tracks operations work.
Everything is kept in one file so it is easy to read and review.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# --------------------------------------------------------------------------
# Configuration - read from environment variables, never hard-coded
# --------------------------------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "apex-operations-api")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

POSTGRES_USER = os.getenv("POSTGRES_USER", "apex")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "apex_operations")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# --------------------------------------------------------------------------
# Logging - structured JSON so logs are easy to search
# --------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, LOG_LEVEL, logging.INFO)),
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger("apex")

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for the table definitions."""


class Operation(Base):
    """One unit of operations work."""

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# SQLite is used by the tests, so the pool options only apply to PostgreSQL.
engine_options: dict[str, object] = {"pool_pre_ping": True, "future": True}
if not DATABASE_URL.startswith("sqlite"):
    engine_options["pool_size"] = 5
    engine_options["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Give each request its own database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> tuple[bool, str | None]:
    """Check the database is reachable. Used by the readiness probe."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - a probe must never raise
        return False, str(exc)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------
app = FastAPI(
    title="Apex Operations API",
    version=APP_VERSION,
    description="Operations tracking API - junior DevOps engineering assessment.",
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Give every request an ID so it can be traced through the logs."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request.failed", method=request.method, path=request.url.path)
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request.completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean error without leaking internal details to the caller."""
    log.exception("unhandled_exception", path=request.url.path)
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred.",
            "request_id": request_id,
        },
    )


@app.on_event("startup")
async def create_tables() -> None:
    """Create the table if it does not exist yet."""
    Base.metadata.create_all(bind=engine)
    log.info("service.started", version=APP_VERSION, environment=APP_ENV)


# --------------------------------------------------------------------------
# Health checks
# --------------------------------------------------------------------------


@app.get("/healthz", tags=["health"])
async def healthz():
    """Liveness check. Proves the process is running."""
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


@app.get("/readyz", tags=["health"])
async def readyz(response: Response):
    """Readiness check. Also proves the database is reachable."""
    db_ok, db_error = check_database()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        log.warning("readiness.failed", database=db_error)
        return {"status": "not_ready", "checks": {"database": "unavailable"}}
    return {"status": "ready", "checks": {"database": "ok"}}


# --------------------------------------------------------------------------
# Operations API
# --------------------------------------------------------------------------


@app.get("/api/v1/operations", tags=["operations"])
async def list_operations(db: Session = Depends(get_db)):
    """List all operations, newest first."""
    rows = db.query(Operation).order_by(Operation.created_at.desc()).all()
    return [
        {
            "id": op.id,
            "reference": op.reference,
            "title": op.title,
            "status": op.status,
            "priority": op.priority,
            "notes": op.notes,
            "created_at": op.created_at,
        }
        for op in rows
    ]


@app.post("/api/v1/operations", status_code=status.HTTP_201_CREATED, tags=["operations"])
async def create_operation(payload: dict, db: Session = Depends(get_db)):
    """Create a new operation."""
    reference = str(payload.get("reference", "")).strip().upper()
    title = str(payload.get("title", "")).strip()

    if not reference or not title:
        raise HTTPException(status_code=400, detail="reference and title are required")

    if db.query(Operation).filter(Operation.reference == reference).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Operation {reference} already exists",
        )

    operation = Operation(
        reference=reference,
        title=title,
        priority=int(payload.get("priority", 3)),
        notes=payload.get("notes"),
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    log.info("operation.created", operation_id=operation.id, reference=operation.reference)

    return {
        "id": operation.id,
        "reference": operation.reference,
        "title": operation.title,
        "status": operation.status,
        "priority": operation.priority,
        "notes": operation.notes,
        "created_at": operation.created_at,
    }


@app.get("/api/v1/operations/{operation_id}", tags=["operations"])
async def get_operation(operation_id: int, db: Session = Depends(get_db)):
    """Fetch one operation by ID."""
    operation = db.get(Operation, operation_id)
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    return {
        "id": operation.id,
        "reference": operation.reference,
        "title": operation.title,
        "status": operation.status,
        "priority": operation.priority,
        "notes": operation.notes,
        "created_at": operation.created_at,
    }


if __name__ == "__main__":
    import uvicorn

    # Binding to 0.0.0.0 is required inside a container so the port is
    # reachable from outside. It is not exposed to the host directly - the
    # container port is published by Docker Compose.
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))  # nosec B104
