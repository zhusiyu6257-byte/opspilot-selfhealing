from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.health import router as health_router
from app.api.v1.assets import router as assets_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 注册 API 路由
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(assets_router, prefix=settings.API_V1_STR)
