from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    PROJECT_NAME: str = "OpsPilot"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # PostgreSQL 配置
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "opspilot_user"
    POSTGRES_PASSWORD: str = "opspilot_password"
    POSTGRES_DB: str = "opspilot_db"

    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # 使用 asyncpg 异步驱动构建数据库连接串
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
