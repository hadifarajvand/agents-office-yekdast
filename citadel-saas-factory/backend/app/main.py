"""Citadel SaaS Factory — FastAPI Application."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.middleware.audit import AuditMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.api.auth import router as auth_router
from app.routes.products import router as products_router
from app.routes.orders import router as orders_router
from app.routes.courses import router as courses_router
from app.routes.webhooks import router as webhooks_router
from app.routes.agents import router as agents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Citadel SaaS Factory",
    description="Cloud education and digital products platform API",
    version="3.0.0",
    lifespan=lifespan,
)

# Middleware stack (executed bottom-to-top)
app.add_middleware(AuditMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(courses_router)
app.include_router(webhooks_router)
app.include_router(agents_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "citadel-saas-factory"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
