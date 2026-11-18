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

    # Alertmanager Webhook 共享密钥。留空 = fail closed（服务端直接拒绝所有
    # 自愈请求），「忘记配置」不能等价于「对全网开放」。
    ALERT_WEBHOOK_TOKEN: str = ""
    # 仅本地开发的显式逃生舱；生产环境必须保持 False
    ALERT_WEBHOOK_ALLOW_INSECURE: bool = False

    # 同一条告警的「冷却时间」：这段时间里最多自愈一次，重复推送直接跳过。
    # 设成 0 = 关掉去重（方便对比演示）。建议小于 Alertmanager 的 repeat_interval。
    ALERT_HEAL_COOLDOWN_SECONDS: int = 600

    # SSH 主机身份校验：默认只连接「指纹已登记」的主机，防止连到冒充机器。
    # 新主机需先把可信指纹写入 known_hosts；不要为图省事长期关闭此开关。
    SSH_STRICT_HOST_KEY_CHECKING: bool = True
    SSH_KNOWN_HOSTS_FILE: str = "~/.ssh/known_hosts"

    # SSH 密码的对称加密主钥匙。留空 = 明确拒绝保存/传递密码（fail closed），
    # 免密密钥登录不受影响。生产应由密钥管理服务注入，绝不提交到仓库。
    SSH_CREDENTIAL_KEY: str = ""

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
