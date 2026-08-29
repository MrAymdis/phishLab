"""企业微信投递引擎单元测试：textcard 渲染、配额 upsert、token 刷新重试、批次任务守卫与状态回写。"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry
from sqlalchemy import delete, select

from app.core.security import encrypt_secret
from app.db.session import SessionLocal
from app.modules.campaign.models import Campaign, CampaignAlert, CampaignBatch, CampaignStat, CampaignTarget
from app.modules.channel.models import SendChannel, SendQuotaUsage
from app.modules.org.models import EmpDept, EmpUser
from worker.tasks.wecom_sender import (
    _alert,
    _quota_inc,
    _quota_remaining,
    _render_textcard,
    _send_with_refresh,
    deliver_wecom_batch,
)

_BASE = 8100


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (CampaignAlert, CampaignTarget, CampaignBatch, CampaignStat,
                  SendQuotaUsage, Campaign, SendChannel, EmpUser, EmpDept):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _channel(db, daily_limit: int = 100) -> SendChannel:
    ch = SendChannel(name="企微通道", type="wecom", wecom_corp_id="ww123",
                     wecom_agent_id="1000002", wecom_secret_enc=encrypt_secret("sec"),
                     daily_limit=daily_limit, status="normal")
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _user(db, uid: int, userid: str | None) -> EmpUser:
    db.add(EmpUser(id=uid, name=f"员工{uid}", email=f"u{uid}@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid=userid))
    db.commit()
    return db.get(EmpUser, uid)


def _campaign(db, cid: int, *, type: str = "social", status: str = "sending",
              channel_id: int | None = None, wecom_template_id: int | None = None) -> Campaign:
    db.add(Campaign(id=cid, name="企微演练", type=type, status=status, creator_id=1,
                    auth_confirmed=1, target_mode="manual", schedule_type="immediate",
                    channel_id=channel_id, wecom_template_id=wecom_template_id))
    db.commit()
    return db.get(Campaign, cid)


def _batch(db, cid: int, status: str = "pending") -> CampaignBatch:
    db.add(CampaignBatch(campaign_id=cid, batch_no=1, plan_at=datetime.now(), status=status))
    db.commit()
    return db.scalar(select(CampaignBatch).where(
        CampaignBatch.campaign_id == cid, CampaignBatch.batch_no == 1))


def _target(db, cid: int, uid: int, status: str = "pending", token: str = "tk1") -> CampaignTarget:
    db.add(CampaignTarget(campaign_id=cid, user_id=uid, batch_no=1, token=token,
                          send_status=status))
    db.commit()
    return db.scalar(select(CampaignTarget).where(
        CampaignTarget.campaign_id == cid, CampaignTarget.user_id == uid))


class _TaskStub:
    """绑定任务 self 桩：request.retries 供退避计算；retry 抛 celery Retry 模拟重跑。"""
    def __init__(self, retries=0):
        self.request = SimpleNamespace(retries=retries)
        self.retried = []

    def retry(self, countdown=None):
        self.retried.append(countdown)
        raise Retry(f"backoff countdown={countdown}")


# ---------- textcard 渲染 ----------

def test_render_textcard_substitutes_vars_and_builds_track_url():
    db = SessionLocal()
    db.add(EmpDept(id=1, name="IT 部", parent_id=0, path="/1/"))
    db.add(EmpUser(id=_BASE + 1, name="张三", email="zs@corp.com", dept_id=1,
                   status=1, initial_risk=70, wecom_userid="zhangsan"))
    campaign = _campaign(db, _BASE + 1)
    tpl = SimpleNamespace(title="{{.FirstName}} 安全演练通知", description="{{.Department}} {{.Date}}",
                          btn_text="立即处理", url_mode="track", custom_url=None)
    user = db.get(EmpUser, _BASE + 1)

    msg = _render_textcard(db, campaign, tpl, user, "tok-abc", "https://track.example.com")
    assert msg["msgtype"] == "textcard"
    assert msg["title"] == "张三 安全演练通知"
    assert "IT 部" in msg["description"] and datetime.now().strftime("%Y-%m-%d") in msg["description"]
    assert msg["btntxt"] == "立即处理"
    assert msg["url"] == "https://track.example.com/t/tok-abc"
    db.close()


def test_render_textcard_custom_url_and_fallback():
    db = SessionLocal()
    campaign = _campaign(db, _BASE + 1)
    user = SimpleNamespace(name="李四", dept_id=None)
    # custom 模式优先自定义地址
    tpl = SimpleNamespace(title="通知", description="摘要", btn_text="查看", url_mode="custom",
                          custom_url="https://custom.example.com/page")
    msg = _render_textcard(db, campaign, tpl, user, "tok-x", "")
    assert msg["url"] == "https://custom.example.com/page"
    # 无追踪域 → dev 直连回退
    msg = _render_textcard(db, campaign, None, user, "tok-x", "")
    assert msg["url"] == f"http://drill-domain.com:8082/t/tok-x"
    assert msg["title"] == "企微演练"  # 无模板时用演练名兜底
    db.close()


# ---------- 配额 ----------

def test_quota_inc_and_remaining_upsert():
    db = SessionLocal()
    # 与投递任务一致：每个目标发送后 commit（autoflush=False，跨 commit 才能看到已插入行）
    _quota_inc(db, 77)
    db.commit()
    _quota_inc(db, 77)
    db.commit()
    row = db.scalar(select(SendQuotaUsage).where(
        SendQuotaUsage.channel_id == 77, SendQuotaUsage.stat_date == date.today()))
    assert row.sent_count == 2

    ch = SimpleNamespace(id=77, daily_limit=5)
    assert _quota_remaining(db, ch) == 3
    ch0 = SimpleNamespace(id=77, daily_limit=0)  # 0 = 不限额
    assert _quota_remaining(db, ch0) >= 10 ** 9
    db.close()


# ---------- token 失效刷新重试 ----------

def test_send_with_refresh_retries_once_on_40014(monkeypatch):
    from app.modules.channel import service as channel_service

    responses = iter([
        {"errcode": 40014, "errmsg": "invalid access_token"},
        {"errcode": 0, "errmsg": "ok"},
    ])
    monkeypatch.setattr(channel_service, "send_wecom_message",
                        lambda db, ch, u, m: next(responses))
    invalidated = []
    monkeypatch.setattr(channel_service, "invalidate_wecom_token", invalidated.append)

    status, reason, action = _send_with_refresh(None, SimpleNamespace(id=1), "u1", {})
    assert (status, action) == ("sent", "sent")
    assert len(invalidated) == 1  # 刷新过一次 token 缓存


def test_send_with_refresh_fails_when_still_invalid_after_refresh(monkeypatch):
    from app.modules.channel import service as channel_service

    monkeypatch.setattr(channel_service, "send_wecom_message",
                        lambda db, ch, u, m: {"errcode": 42001, "errmsg": "expired"})
    monkeypatch.setattr(channel_service, "invalidate_wecom_token", lambda ch: None)

    status, reason, action = _send_with_refresh(None, SimpleNamespace(id=1), "u1", {})
    assert (status, action) == ("failed", "fail")
    assert "仍失效" in reason


# ---------- 批次任务：守卫 + 投递状态回写 ----------

def test_deliver_wecom_batch_ignores_missing_or_done_batch():
    db = SessionLocal()
    assert deliver_wecom_batch.run.__func__(_TaskStub(), 999999, 1) == 0  # 批次不存在
    _campaign(db, _BASE + 1)
    _batch(db, _BASE + 1, status="done")
    assert deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1) == 0  # 已完成批次跳过
    db.close()


def test_deliver_wecom_batch_rejects_non_social_campaign():
    db = SessionLocal()
    _campaign(db, _BASE + 1, type="email")
    _batch(db, _BASE + 1)
    assert deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1) == 0
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "failed"  # 误入企微投递的邮件演练标记失败
    db.close()


def test_deliver_wecom_batch_no_channel_alerts_and_fails():
    db = SessionLocal()
    _campaign(db, _BASE + 1, channel_id=None)
    _batch(db, _BASE + 1)
    assert deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1) == 0
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "failed"
    alert = db.scalar(select(CampaignAlert).where(
        CampaignAlert.campaign_id == _BASE + 1, CampaignAlert.type == "wecom_channel_error"))
    assert alert is not None and "通道" in alert.message
    db.close()


def test_deliver_wecom_batch_skips_target_without_userid(monkeypatch):
    from app.modules.channel import service as channel_service

    sent = []
    monkeypatch.setattr(channel_service, "send_wecom_message",
                        lambda db, ch, u, m: sent.append(u) or {"errcode": 0, "errmsg": "ok"})
    db = SessionLocal()
    ch = _channel(db)
    _campaign(db, _BASE + 1, channel_id=ch.id)
    _batch(db, _BASE + 1)
    _user(db, _BASE + 1, userid=None)  # 无 userid：跳过并告警
    _target(db, _BASE + 1, _BASE + 1)

    result = deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1)
    assert result == 0 and sent == []  # 未发 API 调用
    t = db.scalar(select(CampaignTarget).where(CampaignTarget.campaign_id == _BASE + 1))
    assert t.send_status == "failed" and "userid" in t.fail_reason
    alert = db.scalar(select(CampaignAlert).where(
        CampaignAlert.campaign_id == _BASE + 1, CampaignAlert.type == "wecom_no_userid"))
    assert alert is not None
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "failed"
    db.close()


def test_deliver_wecom_batch_happy_path(monkeypatch):
    from app.modules.channel import service as channel_service

    sent = []
    monkeypatch.setattr(channel_service, "send_wecom_message",
                        lambda db, ch, u, m: sent.append((u, m)) or {"errcode": 0, "errmsg": "ok"})
    db = SessionLocal()
    ch = _channel(db, daily_limit=100)
    _campaign(db, _BASE + 1, channel_id=ch.id)
    _batch(db, _BASE + 1)
    _user(db, _BASE + 1, userid="zhangsan")
    _target(db, _BASE + 1, _BASE + 1)

    result = deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1)
    assert result == 1
    userid, msg = sent[0]
    assert userid == "zhangsan"
    assert msg["msgtype"] == "textcard" and msg["url"].endswith("/t/tk1")

    t = db.scalar(select(CampaignTarget).where(CampaignTarget.campaign_id == _BASE + 1))
    assert t.send_status == "sent" and t.sent_at is not None
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "done" and batch.sent_count == 1
    stat = db.get(CampaignStat, _BASE + 1)
    assert stat is not None and stat.delivered_cnt == 1
    quota = db.scalar(select(SendQuotaUsage).where(
        SendQuotaUsage.channel_id == ch.id, SendQuotaUsage.stat_date == date.today()))
    assert quota.sent_count == 1
    db.close()


def test_deliver_wecom_batch_rate_limit_raises_retry_and_keeps_batch_claimed(monkeypatch):
    from app.modules.channel import service as channel_service

    monkeypatch.setattr(channel_service, "send_wecom_message",
                        lambda db, ch, u, m: {"errcode": 45009, "errmsg": "freq limit"})
    db = SessionLocal()
    ch = _channel(db)
    _campaign(db, _BASE + 1, channel_id=ch.id)
    _batch(db, _BASE + 1, status="sending")  # 派发器已认领
    _user(db, _BASE + 1, userid="zhangsan")
    _target(db, _BASE + 1, _BASE + 1)

    stub = _TaskStub(retries=0)
    with pytest.raises(Retry):
        deliver_wecom_batch.run.__func__(stub, _BASE + 1, 1)
    assert stub.retried == [60]  # 60s × 2^0 退避
    # 批次保持 sending（不重置 pending），派发器不会重复认领 → 无双重投递
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "sending"
    db.close()


def test_deliver_wecom_batch_quota_exhausted_defers_to_tomorrow():
    db = SessionLocal()
    ch = _channel(db, daily_limit=10)
    db.add(SendQuotaUsage(channel_id=ch.id, stat_date=date.today(), sent_count=10))
    _campaign(db, _BASE + 1, channel_id=ch.id)
    _batch(db, _BASE + 1)
    _user(db, _BASE + 1, userid="zhangsan")
    _target(db, _BASE + 1, _BASE + 1)
    db.commit()

    assert deliver_wecom_batch.run.__func__(_TaskStub(), _BASE + 1, 1) == 0
    batch = db.scalar(select(CampaignBatch).where(CampaignBatch.campaign_id == _BASE + 1))
    assert batch.status == "pending"
    assert batch.plan_at.date() > date.today()  # 顺延次日 00:05
    t = db.scalar(select(CampaignTarget).where(CampaignTarget.campaign_id == _BASE + 1))
    assert t.send_status == "pending"  # 目标未动，次日重扫
    db.close()


def test_alert_dedupes_unhandled():
    db = SessionLocal()
    _campaign(db, _BASE + 1)
    _alert(db, _BASE + 1, "wecom_bounce", "userid 不存在")
    db.commit()
    _alert(db, _BASE + 1, "wecom_bounce", "userid 不存在")  # 同类型未处理：去重不重复写
    db.commit()
    count = len(db.scalars(select(CampaignAlert).where(
        CampaignAlert.campaign_id == _BASE + 1, CampaignAlert.type == "wecom_bounce")).all())
    assert count == 1
    db.close()
