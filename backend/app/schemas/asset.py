from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    name: str = Field(..., max_length=64, description="主机名/资产名")
    ip_address: str = Field(..., max_length=45, description="IP地址")
    os_type: str = Field(default="Linux", max_length=32, description="操作系统类型")
    status: str = Field(default="online", max_length=32, description="运行状态")


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    # 允许从 SQLAlchemy ORM 对象直接转换为 Pydantic 字典
    model_config = ConfigDict(from_attributes=True)
