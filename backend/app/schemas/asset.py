from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    name: str = Field(..., max_length=64, description="主机名/资产名")
    ip_address: str = Field(..., max_length=45, description="IP地址")
    os_type: str = Field(default="Linux", max_length=32, description="操作系统类型")
    status: str = Field(default="unknown", max_length=32, description="运行状态")
    ssh_port: int = Field(default=22, ge=1, le=65535, description="SSH 端口")
    ssh_user: str = Field(default="root", max_length=32, description="SSH 登录用户")


class AssetCreate(AssetBase):
    # 只在「写入」方向出现：传入后立即加密，不回显、不落明文
    ssh_password: str | None = Field(
        None,
        description="可选 SSH 密码，加密后保存；留空则沿用免密密钥登录",
    )


class AssetUpdate(BaseModel):
    """编辑资产：字段全部可选，只更新传进来的字段。

    密码语义：
      - 不传 / None：保持原密码不变
      - 传空串 ""：清空已存密码，改回免密密钥登录
      - 传非空串：加密后替换原密码
    """

    name: str | None = Field(None, max_length=64)
    ip_address: str | None = Field(None, max_length=45)
    os_type: str | None = Field(None, max_length=32)
    status: str | None = Field(None, max_length=32)
    ssh_port: int | None = Field(None, ge=1, le=65535)
    ssh_user: str | None = Field(None, max_length=32)
    ssh_password: str | None = Field(
        None, description="不传=保持原密码；空串=清空密码；非空=加密替换"
    )


class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # 只告诉前端「有没有保存凭据」，绝不返回密文本身
    has_stored_password: bool = False

    # 允许从 SQLAlchemy ORM 对象直接转换为 Pydantic 字典
    model_config = ConfigDict(from_attributes=True)
