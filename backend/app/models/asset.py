from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)  # 兼容 IPv4 和 IPv6
    os_type: Mapped[str] = mapped_column(String(32), default="Linux")   # Linux / Windows
    status: Mapped[str] = mapped_column(String(32), default="unknown")  # online / offline / unknown
