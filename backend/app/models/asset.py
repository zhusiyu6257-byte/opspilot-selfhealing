from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, text
from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    ip_address = Column(String(45), nullable=False, unique=True)
    os_type = Column(String(32), default="Linux")
    status = Column(String(16), default="unknown")
    
    # server_default 确保已有旧数据能被自动填充，防止数据库 IntegrityError 抛错
    ssh_port = Column(Integer, default=22, server_default=text("22"), nullable=False)
    ssh_user = Column(String(32), default="root", server_default=text("'root'"), nullable=False)
    # 只存 Fernet 密文；None = 沿用免密密钥登录。明文密码任何时刻都不落库。
    ssh_password_encrypted = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
