"""BloodLink - Smart Blood & Emergency Donor Network. Starts the backend application.

Run:  uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from database import Base, engine, SessionLocal
from auth import require_roles
from models import User
from routers import auth_routes, request_routes, donor_routes, admin_routes
from services.request_manager import maintain

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bloodlink")
MAINTENANCE_SECONDS = int(os.getenv("MAINTENANCE_SECONDS", "60"))
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


async def maintenance_loop():
    """Background scheduler: escalates unanswered waves and expires overdue requests."""
    while True:
        await asyncio.sleep(MAINTENANCE_SECONDS)
        db = SessionLocal()
        try:
            result = maintain(db)
            if any(result.values()):
                log.info("maintenance: %s", result)
        except Exception as e:  # keep the loop alive no matter what
            log.exception("maintenance failed: %s", e)
            db.rollback()
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if DEMO_MODE and db.query(User).count() == 0:
            from seed import seed
            log.info("Empty database - loading demo data: %s", seed(db))
    finally:
        db.close()
    task = asyncio.create_task(maintenance_loop())
    yield
    task.cancel()


app = FastAPI(title="BloodLink - Smart Blood & Emergency Donor Network", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth_routes, request_routes, donor_routes, admin_routes):
    app.include_router(r.router)


@app.exception_handler(SQLAlchemyError)
async def db_error(request: Request, exc: SQLAlchemyError):
    log.exception("Database error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Database error - please try again"})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/maintenance/run")
def run_maintenance():
    """Lets the demo trigger escalation/expiry immediately instead of waiting for the scheduler."""
    db = SessionLocal()
    try:
        return maintain(db)
    finally:
        db.close()


@app.post("/api/demo/reset")
def demo_reset(user: User = Depends(require_roles("admin"))):
    """Admin-only: wipe everything and reload demo data (handy between demo rehearsals)."""
    if os.getenv("DEMO_MODE", "true").lower() != "true":
        raise HTTPException(403, "Demo reset is disabled")
    from seed import reset_and_seed
    return reset_and_seed()


# Serve the built React app (frontend/dist) from the same server in production
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
