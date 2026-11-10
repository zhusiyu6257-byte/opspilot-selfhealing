from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis import get_redis

router = APIRouter(tags=["Health"])


@router.get("/healthz")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    health_data = {
        "status": "healthy",
        "postgres": "unknown",
        "redis": "unknown",
    }

    # 1. 检查数据库连通性
    try:
        await db.execute(text("SELECT 1"))
        health_data["postgres"] = "connected"
    except Exception as exc:
        health_data["postgres"] = f"unhealthy: {str(exc)}"
        health_data["status"] = "unhealthy"

    # 2. 检查 Redis 连通性
    try:
        pong = await redis.ping()
        if pong:
            health_data["redis"] = "connected"
    except Exception as exc:
        health_data["redis"] = f"unhealthy: {str(exc)}"
        health_data["status"] = "unhealthy"

    # 若任一组件异常，返回 HTTP 503 Service Unavailable，供探针精准识别
    status_code = (
        status.HTTP_200_OK
        if health_data["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=health_data)
