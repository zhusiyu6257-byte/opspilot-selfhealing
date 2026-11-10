from redis.asyncio import Redis
from app.core.config import settings

redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)

async def get_redis() -> Redis:
    """供 FastAPI 路由依赖注入调用的 Redis 客户端"""
    return redis_client
