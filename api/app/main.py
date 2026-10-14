from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.app.config import settings
from api.app.services.supabase import get_supabase_service, SupabaseService

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-quality FastAPI backend for Nexora",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

@app.get("/api/v1/health/supabase")
def supabase_health_check(
    service: SupabaseService = Depends(get_supabase_service)
):
    return service.get_diagnostics()

# Register Routers
from api.app.routes import auth_router, users_router, courses_router
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(courses_router)


