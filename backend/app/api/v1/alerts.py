import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.command_guard import UnsafeCommandError, assert_safe_command
from app.core.config import settings
from app.core.heal_dedup import release, try_claim
from app.core.webhook_auth import require_alert_token
from app.db.session import get_db
from app.models.asset import Asset
from app.models.execution import TaskExecution
from app.tasks.runbook import execute_command_task

router = APIRouter(prefix="/alerts", tags=["Alerts & Self-Healing"])

# 预设的自愈规则映射字典 (Alert Rule -> 自愈 Shell 脚本)
HEALING_PLAYBOOKS: Dict[str, str] = {
    # 磁盘告警：清理 /tmp 目录下的临时垃圾文件并回收空间
    "DiskUsageHigh": "rm -rf /tmp/mock_junk_* /tmp/*.log 2>/dev/null || true; df -h /",
    # 探活失败/服务异常：尝试重启关键服务
    "ServiceDown": "systemctl is-active ssh || sudo service ssh restart; uptime",
    # 默认巡检剧本：收集系统核心负载与状态快照
    "DefaultInspection": "uptime && free -m && df -h",
}


# 标准 Prometheus/Alertmanager Webhook Payload 数据结构
class AlertItem(BaseModel):
    status: str  # "firing" 或 "resolved"
    labels: Dict[str, str]  # 如 {"alertname": "DiskUsageHigh", "instance": "127.0.0.1:9100", "ip": "127.0.0.1"}
    annotations: Optional[Dict[str, str]] = None
    startsAt: Optional[str] = None


class AlertmanagerWebhookPayload(BaseModel):
    version: Optional[str] = "4"
    status: str  # "firing" | "resolved"
    receiver: Optional[str] = "opspilot-webhook"
    alerts: List[AlertItem]


# 鉴权挂在路由级依赖上：在派发 Celery / 写审计之前拒绝，
# 业务函数只关心「告警要跑哪条剧本」，不混入凭证解析。
@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_alert_token)],
)
async def handle_alertmanager_webhook(
    payload: AlertmanagerWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    接收 Prometheus Alertmanager 告警 Webhook，自动触发对应的自愈剧本
    """
    dispatched_tasks = []
    rejected_tasks = []
    skipped_tasks = []

    for alert in payload.alerts:
        # 只处理正在触发中的告警（firing），忽略已恢复（resolved）
        if alert.status != "firing":
            continue

        alert_name = alert.labels.get("alertname", "Unknown")
        # 优先从 labels 中抓取机器 IP（支持 ip、node、instance: "127.0.0.1:9100" 格式截取）
        target_ip = alert.labels.get("ip") or alert.labels.get("instance", "").split(":")[0]

        if not target_ip:
            continue

        # 1. 查找数据库中被纳管的资产
        result = await db.execute(select(Asset).where(Asset.ip_address == target_ip))
        asset = result.scalars().first()
        if not asset:
            # 该 IP 未纳管，跳过自愈
            continue

        # 2. 规则匹配：从剧本库获取修复脚本，未匹配则执行默认快照巡检
        heal_command = HEALING_PLAYBOOKS.get(alert_name, HEALING_PLAYBOOKS["DefaultInspection"])

        # 剧本库虽然写在代码里，也必须过同一道护栏：
        # 以后有人把某条剧本误改成 rm -rf / 时，这里能挡住并留下可读原因。
        try:
            assert_safe_command(heal_command)
        except UnsafeCommandError as exc:
            # 与手动入口一致：拒绝写一条 REJECTED 审计，让「哪条剧本被拦」
            # 可查询。这里已过 Token 鉴权，写入方可信，不存在被刷库的风险。
            db.add(TaskExecution(
                task_id=uuid.uuid4().hex,
                asset_id=asset.id,
                task_type="AUTO_HEAL",
                command=heal_command,
                trigger_source="ALERT_WEBHOOK",
                status="REJECTED",
                stderr=f"[安全护栏] {exc}",
            ))
            await db.commit()
            rejected_tasks.append({
                "alertname": alert_name,
                "target_ip": target_ip,
                "reason": str(exc),
            })
            continue

        # 3. 冷却去重：同一条告警在冷却期内只自愈一次。
        # 放在护栏之后是刻意的：被拦下的剧本不该占名额，否则把剧本改对了
        # 冷却期内依然跑不起来。
        identity = {
            "labels": alert.labels,
            "startsAt": alert.startsAt,
            "command": heal_command,
        }
        claimed, dedup_key = await try_claim(identity)
        if not claimed:
            skipped_tasks.append({
                "alertname": alert_name,
                "target_ip": target_ip,
                "reason": f"冷却期内已自愈过（{settings.ALERT_HEAL_COOLDOWN_SECONDS} 秒），本次跳过",
            })
            continue

        # 4. 先落审计再派发：与手动入口同一原则。记录先提交进库，
        #    worker 无论抢跑多快都能按 task_id 找到这条 PENDING。
        task_id = uuid.uuid4().hex
        execution_record = TaskExecution(
            task_id=task_id,
            asset_id=asset.id,
            task_type="AUTO_HEAL",
            command=heal_command,
            trigger_source="ALERT_WEBHOOK",
            status="PENDING",
        )
        db.add(execution_record)
        await db.commit()

        # 5. 派发时显式携带同一个任务号，worker 的 self.request.id 即它。
        try:
            execute_command_task.apply_async(
                kwargs={
                    "asset_id": asset.id,
                    "hostname": asset.ip_address,
                    "port": asset.ssh_port,
                    "username": asset.ssh_user,
                    "command": heal_command,
                    # 自愈没有人工输入密码：直接把主机已存的密文信封交给
                    # Worker，API 侧无需解出明文，队列里也不会出现明文。
                    "password_envelope": asset.ssh_password_encrypted or "",
                    "trigger_source": "ALERT_WEBHOOK",
                    # 告警名随任务带到 Worker，用于结果通知的标题与分类
                    "alert_name": alert_name,
                },
                task_id=task_id,
            )
        except Exception as exc:
            # 活儿没派出去：登记退还名额，审计改判 FAILED（不删记录，
            # 「派发失败」是事实）。派发成功后即使后面出错也不擦：
            # 擦登记会导致重复远程执行。
            await release(dedup_key)
            execution_record.status = "FAILED"
            execution_record.stderr = f"[派发失败] {exc}"
            execution_record.finished_at = datetime.utcnow()
            await db.commit()
            rejected_tasks.append({
                "alertname": alert_name,
                "target_ip": target_ip,
                "reason": f"派发失败，已退还名额：{exc}",
            })
            continue

        dispatched_tasks.append({
            "alertname": alert_name,
            "target_ip": target_ip,
            "task_id": task_id,
            "command": heal_command,
        })

    await db.commit()

    return {
        "status": "success" if not rejected_tasks else "partial_rejected",
        "processed_count": len(dispatched_tasks),
        "dispatched_tasks": dispatched_tasks,
        "rejected_count": len(rejected_tasks),
        "rejected_tasks": rejected_tasks,
        "skipped_count": len(skipped_tasks),
        "skipped_tasks": skipped_tasks,
    }
