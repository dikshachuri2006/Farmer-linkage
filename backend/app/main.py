from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.buyer import router as buyer_router
from app.routes.crops import router as crops_router
from app.routes.farmer import router as farmer_router
from app.routes.markets import router as markets_router
from app.routes.marketplace import router as marketplace_router
from app.routes.notifications import router as notifications_router
from app.routes.price_discovery import router as price_discovery_router
from app.routes.prices import router as prices_router
from app.routes.price_predictions import router as price_predictions_router
from app.routes.complaints import router as complaints_router
from app.routes.transactions import router as transactions_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Backend API for SIH Problem Statement SIH26132: "
        "Strengthening Market Linkage and Price Discovery of Farmer. "
        "Enables secure trade, multi-market comparison, and net-realization discovery."
    ),
    version=settings.VERSION,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS configuration for frontend (Diksha)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers under API_V1_STR prefix (/api)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(farmer_router, prefix=settings.API_V1_STR)
app.include_router(buyer_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(crops_router, prefix=settings.API_V1_STR)
app.include_router(markets_router, prefix=settings.API_V1_STR)
app.include_router(marketplace_router, prefix=settings.API_V1_STR)
app.include_router(prices_router, prefix=settings.API_V1_STR)
app.include_router(price_predictions_router, prefix=settings.API_V1_STR)
app.include_router(price_discovery_router, prefix=settings.API_V1_STR)
app.include_router(transactions_router, prefix=settings.API_V1_STR)
app.include_router(complaints_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)


from pathlib import Path
from fastapi.staticfiles import StaticFiles

@app.get("/api", tags=["Health"])
def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": f"{settings.API_V1_STR}/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }


# Mount frontend static directory to serve both frontend and backend on the same port
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

