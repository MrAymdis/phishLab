"""企业微信投递引擎任务：批次调度、频控退避、errcode 映射、幂等重试。

设计稿《企业微信通道设计方案》§6.1：
- 0        → sent（企微无已读回执，sent 即终态；delivered 不适用）
- 40014/42001 → access_token 失效：强制刷新后重试一次
- 45009/45024 → 频控：指数退避（60s 起 ×2，封顶 30min），批次重跑只扫 pending 目标（幂等）
- 60111   → userid 不存在 → bounced + 告警
- 60011/60020 等应用级错误 → failed + 告警（人工介入，不无限重试）

配额：SendQuotaUsage（channel_id + 日期）累计当日成功发送数，超 daily_limit 批次顺延至次日。
"""
import logging
import random
import time
from datetime import date, datetime, timedelta

from sqlalchemy import select
from celery.exceptions import MaxRetriesExceededError, Retry

from app.db.stat_upsert import stat_inc
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.wecom")

# 企微 API 逐条间隔抖动（秒）：企微对单应用有调用频率限制，打散瞬时连发
_SEND_JITTER_SEC = (0.2, 0.8)

# 频控退避：60s 起 ×2 封顶 30min（Celery retry countdown 秒）
_RATE_BACKOFF_BASE = 60
_RATE_BACKOFF_CAP = 1800

# 应用级错误：整个通道不可用，告警人工介入（不逐目标重试）
_FATAL_ERRCODES = {"60011", "60020", "48001", "60003", "60008", "82001", "41005", "40008"}


def _pick_wecom_channel(db, campaign):
    """演练指定通道（wecom）→ 默认 wecom 通道。"""
    from app.modules.channel.models import SendChannel

    ch = db.get(SendChannel, campaign.channel_id) if campaign.channel_id else None
    if ch and ch.type == "wecom":
        return ch
    return db.scalar(
        select(SendChannel).where(SendChannel.type == "wecom").order_by(SendChannel.is_default.desc(), SendChannel.id)
    )


def _render_textcard(db, campaign, tpl, user, token: str, track_base: str) -> dict:
    """按企微模板渲染 textcard 消息体：模板变量与邮件渲染同约定（{{.FirstName}} 等）。

    url_mode=track → /t/{token} 追踪短链（click 复用现有链路）；custom → 自定义地址。
    """
    from app.modules.org.models import EmpDept

    dept = db.get(EmpDept, user.dept_id) if user and user.dept_id else None
    if tpl is not None and tpl.url_mode == "custom" and tpl.custom_url:
        reset_url = tpl.custom_url
    elif track_base:
        reset_url = f"{track_base}/t/{token}"
    else:
        # 追踪域未配置：dev 演示直连（与 render.py 邮件渲染同约定）
        from app.modules.settings.service import get_setting

        drill_domain = get_setting(db, "drill_domain", "drill-domain.com")
        from app.core.config import settings

        reset_url = f"http://{drill_domain}:{settings.landing_port}/t/{token}"
    var_map = {
        "{{.FirstName}}": user.name if user else "同事",
        "{{.Department}}": dept.name if dept else "",
        "{{.Date}}": datetime.now().strftime("%Y-%m-%d"),
        "{{.ResetURL}}": reset_url,
    }
    title = (tpl.title if tpl and tpl.title else campaign.name)
    description = (tpl.description if tpl and tpl.description else "点击下方按钮查看详情")
    btn_text = (tpl.btn_text if tpl and tpl.btn_text else "查看详情")
    for k, v in var_map.items():
        title = title.replace(k, v)
        description = description.replace(k, v)
        btn_text = btn_text.replace(k, v)
    return {
        "msgtype": "textcard",
        "title": title[:128],
        "description": description[:512],
        "btntxt": btn_text[:16],
        "url": reset_url,
    }


def _quota_inc(db, channel_id: int) -> None:
    """当日成功发送数 +1（SendQuotaUsage upsert，MySQL 原子累加 / SQLite 回退）。"""
    from app.db.session import engine
    from app.modules.channel.models import SendQuotaUsage

    today = date.today()
    if engine.dialect.name == "mysql":
        from sqlalchemy import func
        from sqlalchemy.dialects.mysql import insert

        stmt = insert(SendQuotaUsage).values(
            channel_id=channel_id, stat_date=today, sent_count=1)
        db.execute(stmt.on_duplicate_key_update(
            sent_count=func.greatest(SendQuotaUsage.sent_count + 1, 0)))
        return
    row = db.scalar(select(SendQuotaUsage).where(
        SendQuotaUsage.channel_id == channel_id, SendQuotaUsage.stat_date == today))
    if row is None:
        db.add(SendQuotaUsage(channel_id=channel_id, stat_date=today, sent_count=1))
    else:
        row.sent_count += 1


def _quota_remaining(db, ch) -> int:
    """当日剩余配额（daily_limit - 已发送）；daily_limit=0 视为不限额。"""
    from app.modules.channel.models import SendQuotaUsage

    if not ch.daily_limit:
        return 10 ** 9
    row = db.scalar(select(SendQuotaUsage).where(
        SendQuotaUsage.channel_id == ch.id, SendQuotaUsage.stat_date == date.today()))
    used = row.sent_count if row else 0
    return max(ch.daily_limit - used, 0)


def _alert(db, campaign_id: int, alert_type: str, message: str, target_user_id: int | None = None) -> None:
    """演练预警落库（去重：同类型未处理告警存在则不重复写）。"""
    from sqlalchemy import exists
    from app.modules.campaign.models import CampaignAlert

    dup = db.scalar(select(exists().where(
        CampaignAlert.campaign_id == campaign_id,
        CampaignAlert.type == alert_type,
        CampaignAlert.handled == 0,
    )))
    if dup:
        return
    db.add(CampaignAlert(campaign_id=campaign_id, type=alert_type, level=2,
                         message=message[:512], target_user_id=target_user_id))


def _send_with_refresh(db, ch, userid: str, msg: dict) -> tuple[str, str, str]:
    """发送 + 40014/42001 时强制刷新 token 重试一次。返回 (status, reason, action)。"""
    from app.modules.channel.service import invalidate_wecom_token, send_wecom_message, wecom_send_status

    status, reason, action = wecom_send_status(send_wecom_message(db, ch, userid, msg))
    if action == "refresh":
        invalidate_wecom_token(ch)
        logger.warning("wecom token 失效已刷新重试 channel=%s", ch.id)
        status, reason, action = wecom_send_status(send_wecom_message(db, ch, userid, msg))
        if action == "refresh":
            status, reason, action = "failed", f"{reason}（刷新 token 后仍失效）", "fail"
    return status, reason, action


def _reset_batch_pending(db, campaign_id: int, batch_no: int, delay_min: int) -> None:
    """批次回退 pending 并顺延 plan_at，派发器重扫（目标行 send_status=pending 兜底幂等）。"""
    from app.modules.campaign.models import CampaignBatch

    batch = db.scalar(select(CampaignBatch).where(
        CampaignBatch.campaign_id == campaign_id, CampaignBatch.batch_no == batch_no))
    if batch is not None and batch.status == "sending":
        batch.status = "pending"
        batch.plan_at = datetime.now() + timedelta(minutes=delay_min)
        db.commit()


@celery_app.task(name="worker.tasks.wecom_sender.deliver_wecom_batch",
                 bind=True, max_retries=6)
def deliver_wecom_batch(self, campaign_id: int, batch_no: int):
    """投递企微演练批次：textcard 渲染 → message/send → errcode 映射 → 状态/配额/告警回写。

    幂等：只扫 send_status=pending 的目标；已 sent/bounced/failed 的目标重跑时跳过。
    """
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignBatch, CampaignTarget
    from app.modules.template.models import WecomTemplate

    db = SessionLocal()
    try:
        batch = db.scalar(select(CampaignBatch).where(
            CampaignBatch.campaign_id == campaign_id, CampaignBatch.batch_no == batch_no))
        if batch is None or batch.status not in ("pending", "sending"):
            return 0  # 不存在或已完成：防重复执行
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return 0
        if campaign.status not in ("sending", "running"):
            batch.status = "pending"  # 演练暂停/终止：不真实发信，resume 后恢复
            db.commit()
            return 0
        if campaign.type != "social":
            batch.status = "failed"
            db.commit()
            logger.error("非 social 演练误入企微投递 campaign=%s", campaign_id)
            return 0

        ch = _pick_wecom_channel(db, campaign)
        if ch is None:
            batch.status = "failed"
            _alert(db, campaign_id, "wecom_channel_error", "无可用企业微信发送通道")
            db.commit()
            return 0
        # 配额：超 daily_limit 顺延至次日（channel 模型注释约定）
        remaining = _quota_remaining(db, ch)
        if remaining <= 0:
            batch.status = "pending"
            tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            batch.plan_at = tomorrow
            db.commit()
            logger.warning("wecom 通道当日配额耗尽，批次顺延至次日 channel=%s", ch.id)
            return 0

        tpl = db.get(WecomTemplate, campaign.wecom_template_id) if campaign.wecom_template_id else None
        if tpl is not None and tpl.msg_type != "textcard":
            batch.status = "failed"
            _alert(db, campaign_id, "wecom_channel_error", f"企微模板 {tpl.name} 消息类型 {tpl.msg_type} 暂不支持（P0 仅 textcard）")
            db.commit()
            return 0

        from app.modules.settings.service import resolve_track_urls

        track_base, _ = resolve_track_urls(db, campaign)

        targets = db.scalars(select(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.batch_no == batch_no,
            CampaignTarget.send_status == "pending",
        )).all()
        random.shuffle(targets)  # 打散投递顺序，避免按名单顺序连发

        from app.modules.org.models import EmpUser

        users = {u.id: u for u in db.scalars(
            select(EmpUser).where(EmpUser.id.in_([t.user_id for t in targets]))).all()}

        sent = failed = 0
        batch_alerted = False  # 应用级错误整批只告警一次
        no_userid_alerted = False
        # 演练高级设置 time_jitter_sec 优先；未配置回退内置小抖动（企微频控）
        # 函数级导入避免与 delivery 模块的循环依赖
        from worker.tasks.delivery import _inter_target_delay_sec

        for idx, t in enumerate(targets):
            if idx > 0:
                time.sleep(random.uniform(*_inter_target_delay_sec(campaign)))
            user = users.get(t.user_id)
            if user is None or not user.wecom_userid:
                t.send_status = "failed"
                t.fail_reason = "员工未配置企业微信 userid，无法投递"
                if not no_userid_alerted:
                    _alert(db, campaign_id, "wecom_no_userid",
                           f"批次 {batch_no} 存在未配置 userid 的目标员工，已跳过（{t.fail_reason}）")
                    no_userid_alerted = True
                db.commit()
                failed += 1
                continue
            msg = _render_textcard(db, campaign, tpl, user, t.token, track_base)
            try:
                status, reason, action = _send_with_refresh(db, ch, user.wecom_userid, msg)
            except Exception as err:
                db.rollback()
                logger.exception("wecom 发送异常 target=%s", t.id)
                stale = db.get(CampaignTarget, t.id)
                if stale is not None:
                    stale.send_status = "failed"
                    stale.fail_reason = f"投递异常：{str(err)}"[:500]
                    db.commit()
                failed += 1
                continue
            if action == "backoff":
                # 频控：指数退避重跑整个批次（已 sent 目标被 pending 过滤，幂等）
                db.rollback()
                countdown = min(_RATE_BACKOFF_BASE * (2 ** self.request.retries), _RATE_BACKOFF_CAP)
                logger.warning("wecom 频控退避 campaign=%s batch=%s retry=%s countdown=%ss",
                               campaign_id, batch_no, self.request.retries, countdown)
                raise self.retry(countdown=countdown)
            if status == "sent":
                t.send_status = "sent"
                t.fail_reason = None
                t.sent_at = datetime.now()
                stat_inc(db, campaign_id, delivered_cnt=1)
                _quota_inc(db, ch.id)
                db.commit()
                sent += 1
            elif status == "bounced":
                t.send_status = "bounced"
                t.fail_reason = reason[:500]
                _alert(db, campaign_id, "wecom_bounce", reason, t.user_id)
                db.commit()
                failed += 1
            else:  # failed
                t.send_status = "failed"
                t.fail_reason = reason[:500]
                if not batch_alerted:
                    _alert(db, campaign_id, "wecom_channel_error", f"企微通道投递错误：{reason}")
                    batch_alerted = True
                db.commit()
                failed += 1
            if sent >= remaining:  # 本批次内配额耗尽：剩余目标保持 pending，次日顺延
                batch.status = "pending"
                tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
                batch.plan_at = tomorrow
                db.commit()
                logger.warning("wecom 配额在批次中途耗尽，剩余目标次日顺延 campaign=%s batch=%s", campaign_id, batch_no)
                return sent

        batch.status = "done" if failed == 0 else "failed"
        batch.sent_count = sent
        batch.started_at = batch.started_at or datetime.now()
        batch.finished_at = datetime.now()
        db.commit()
        logger.info("deliver_wecom_batch campaign=%s batch=%s sent=%d failed=%d",
                    campaign_id, batch_no, sent, failed)
        return sent
    except MaxRetriesExceededError:
        db.rollback()
        _reset_batch_pending(db, campaign_id, batch_no, delay_min=30)
        logger.error("wecom 频控重试耗尽，批次顺延 30 分钟 campaign=%s batch=%s", campaign_id, batch_no)
        return 0
    except Retry:
        # 频控退避重跑：批次保持 sending（派发器不重复认领），已 sent 目标按 pending 过滤幂等
        raise
    except Exception:
        db.rollback()
        _reset_batch_pending(db, campaign_id, batch_no, delay_min=5)
        raise
    finally:
        db.close()
