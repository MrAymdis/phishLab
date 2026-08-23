"""数据留存清理任务（合规红线：留存期到期自动匿名化/删除）。

platform_setting 三类留存配置（默认 drill 180d / behavior 180d / log 1y）：
- retention_drill  ：演练数据 → track_event 事件明细（IP/UA/指纹/提交表单）、
                      campaign_target 对象明细（仅已完成/终止演练，按演练创建时间计）
- retention_behavior：行为指纹 → fingerprint 设备指纹（last_seen_at 超期）
- retention_log    ：日志与 AI 会话 → audit_log / login_log / open_api_log / ai_message

演练汇总（campaign_stat）与 stat_daily 日归档不受影响，长期趋势在清理后仍可回放；
审计留痕 account=None（worker 自动任务）。
MinIO eml/导出文件：当前无 MinIO 接线（文件落本地 static 目录），无需同步清理。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.core.audit import record_audit
from app.db.session import SessionLocal
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.retention")

_DEFAULT_DAYS = {"drill": 180, "behavior": 180, "log": 365}


def _parse_days(value) -> int | None:
    """解析留存期配置：'180d' / '6m' / '1y' → 天数；非法值返回 None（走默认）。"""
    if not value:
        return None
    s = str(value).strip().lower()
    try:
        n = float(s[:-1])
        unit = s[-1]
    except (ValueError, IndexError):
        return None
    if unit == "d":
        return int(n)
    if unit == "m":
        return int(n * 30)
    if unit == "y":
        return int(n * 365)
    return None


_CHUNK = 5000


@celery_app.task(name="worker.tasks.retention_clean.clean")
def clean():
    """到期数据清理（beat 每日 03:00 调度）：按三类留存期删除超期数据。"""
    from app.modules.account.models import LoginLog
    from app.modules.ai.models import AiMessage
    from app.modules.campaign.models import Campaign, CampaignTarget
    from app.modules.openapi_mod.models import OpenApiLog
    from app.modules.rbac.models import AuditLog
    from app.modules.settings.models import PlatformSetting
    from app.modules.tracking.models import Fingerprint, TrackEvent

    db = SessionLocal()
    try:
        cfg = dict(db.execute(
            select(PlatformSetting.setting_key, PlatformSetting.setting_value)
            .where(PlatformSetting.setting_key.in_(
                ("retention_drill", "retention_behavior", "retention_log")))
        ).all())
        now = datetime.now()
        drill_cut = now - timedelta(days=_parse_days(cfg.get("retention_drill")) or _DEFAULT_DAYS["drill"])
        behavior_cut = now - timedelta(days=_parse_days(cfg.get("retention_behavior")) or _DEFAULT_DAYS["behavior"])
        log_cut = now - timedelta(days=_parse_days(cfg.get("retention_log")) or _DEFAULT_DAYS["log"])

        counts: dict[str, int] = {}

        def _del(name: str, model, where):
            """分批删除超期行（每批 _CHUNK 条、逐批提交）。

            track_event 等表可达百万行，单条 DELETE 会锁大范围行 + undo 日志暴涨；
            分批后每批行锁小，任务中断后重跑可续删（幂等：条件基于时间）。
            """
            pk = model.__table__.primary_key.columns[0]
            n = 0
            while True:
                ids = db.scalars(select(pk).where(where).limit(_CHUNK)).all()
                if not ids:
                    break
                n += db.execute(delete(model).where(pk.in_(ids))).rowcount or 0
                db.commit()
            counts[name] = n
            if n > _CHUNK:
                logger.info("retention %s 分批删除 %s 条（chunk=%s）", name, n, _CHUNK)

        # 演练数据：事件明细（含 IP/UA/指纹/提交表单密文）
        _del("track_event", TrackEvent, TrackEvent.created_at < drill_cut)
        # 演练数据：对象明细（仅已完成/终止演练；进行中演练即使超期也不动）
        done_ids = select(Campaign.id).where(
            Campaign.status.in_(("completed", "terminated")),
            Campaign.created_at < drill_cut,
        )
        _del("campaign_target", CampaignTarget,
             CampaignTarget.campaign_id.in_(done_ids))
        # 行为指纹：last_seen 超期即删（事件同步删除，无悬挂引用）
        _del("fingerprint", Fingerprint, Fingerprint.last_seen_at < behavior_cut)
        # 日志与 AI 会话
        _del("audit_log", AuditLog, AuditLog.created_at < log_cut)
        _del("login_log", LoginLog, LoginLog.created_at < log_cut)
        _del("open_api_log", OpenApiLog, OpenApiLog.created_at < log_cut)
        _del("ai_message", AiMessage, AiMessage.created_at < log_cut)
        total = sum(counts.values())
        if total:
            logger.info("留存清理完成：共 %s 条 %s", total, counts)
        record_audit(
            db, account=None, module="system", action="retention_clean",
            target_type="platform_setting", target_id="retention",
            detail={
                "cutoffs": {
                    "drill": drill_cut.strftime("%Y-%m-%d"),
                    "behavior": behavior_cut.strftime("%Y-%m-%d"),
                    "log": log_cut.strftime("%Y-%m-%d"),
                },
                "counts": counts,
            },
        )
        db.commit()  # 审计留痕（各表删除已在分批循环内逐批提交）
        return total
    except Exception:
        db.rollback()
        logger.exception("留存清理失败")
        raise
    finally:
        db.close()
