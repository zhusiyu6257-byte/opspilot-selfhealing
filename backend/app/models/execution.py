from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    
    # 任务元数据
    task_type = Column(String(32), default="COMMAND", nullable=False)  # COMMAND / PING / AUTO_HEAL
    command = Column(Text, nullable=True)
    trigger_source = Column(String(32), default="MANUAL", nullable=False)  # MANUAL / ALERT_WEBHOOK / CRON
    
    # 执行状态机: PENDING -> RUNNING -> SUCCESS / FAILED
    # REJECTED 是入口拒绝的终态：命令从未派发执行，但拒绝本身可查询
    status = Column(String(16), default="PENDING", index=True, nullable=False)
    exit_code = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    # 关联资产表
    asset = relationship("Asset", backref="executions")
