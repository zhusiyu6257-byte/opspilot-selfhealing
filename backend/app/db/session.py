from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

# 创建异步数据库引擎
# pool_pre_ping=True: 每次从池子取连接前发心跳，避免取出因超时断开的死连接
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# 异步 Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """供 FastAPI 路由依赖注入调用的 DB 会话生成器"""
    async with AsyncSessionLocal() as session:
        yield session
