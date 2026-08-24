"""attach_run 事件消费测试：落库 + 目标计数 + 冗余计数 + 风险画像 + 去重。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.modules.campaign.models import Campaign, CampaignAlert, CampaignAttachment, CampaignStat, CampaignTarget
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.template.models import AttachmentDownloadLog, AttachmentPayload, EmailTemplate
from app.modules.tracking.models import TrackEvent
from app.modules.tracking.stream import push_event
from worker.tasks.track_stream import consume


@pytest.fixture(autouse=True)
def _cleanup():
    """每个用例后清空测试数据：固定邮箱/token 在同库内二次执行会撞唯一约束。"""
    yield
    db = SessionLocal()
    try:
        for m in (TrackEvent, EmpRiskProfile, CampaignAlert, CampaignTarget, CampaignAttachment,
                  CampaignStat, Campaign, EmpUser, EmpDept, EmailTemplate,
                  AttachmentPayload, AttachmentDownloadLog):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _setup():
    db = SessionLocal()
    tpl = EmailTemplate(name="t", scene="finance", subject="s", html_body="<p>x</p>")
    db.add(tpl)
    db.flush()
    dept = EmpDept(name="财务部", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="李四", email="lisi@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    c = Campaign(name="附件演练", type="mail", creator_id=1, template_id=tpl.id,
                 target_mode="dept", target_snapshot={})
    db.add(c)
    db.flush()
    t = CampaignTarget(campaign_id=c.id, user_id=user.id, token="b" * 32)
    db.add(t)
    db.add(CampaignStat(campaign_id=c.id))
    db.commit()
    db.close()
    return c.id, t.id, user.id, t.token


def test_attach_run_consumed_and_counted():
    cid, tid, uid, token = _setup()
    push_event(token=token, event_type="attach_run", ip="1.2.3.4", ua="Word/16.0",
               detail={"filename": "工资条.docx", "mode": "beacon"})
    consume()

    db = SessionLocal()
    try:
        events = db.scalars(select(TrackEvent).where(TrackEvent.token == token)).all()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == "attach_run"
        assert ev.detail == {"filename": "工资条.docx", "mode": "beacon"}
        assert ev.ip == "1.2.3.4"
        assert ev.campaign_id == cid and ev.user_id == uid

        t = db.get(CampaignTarget, tid)
        assert t.attach_run_count == 1
        assert t.first_attach_run_at is not None and t.last_attach_run_at is not None

        stat = db.get(CampaignStat, cid)
        assert stat.attach_cnt == 1

        profile = db.scalar(select(EmpRiskProfile).where(EmpRiskProfile.user_id == uid))
        assert profile is not None
        assert profile.attach_run == 80  # 初始 70 + 10

        # 附件运行=中招（高危）：产生预警 + 计入综合评分（×10）
        alert = db.scalar(select(CampaignAlert).where(CampaignAlert.campaign_id == cid))
        assert alert is not None and alert.type == "attach_run" and alert.level == 3
        assert "运行" in alert.message
        assert profile.total_score == 80  # 初始 70 + attach_run×10（新增权重）
        assert profile.risk_level == 2  # 80 分 → 中风险（71-80）
    finally:
        db.close()


def test_attach_run_dedup_window():
    _cid, tid, _uid, token = _setup()
    push_event(token=token, event_type="attach_run")
    consume()
    push_event(token=token, event_type="attach_run")  # 60s 窗口内重复
    consume()

    db = SessionLocal()
    try:
        n = db.scalar(select(TrackEvent.id).where(
            TrackEvent.token == token, TrackEvent.event_type == "attach_run").limit(1))
        assert n is not None  # 首条已落库
        t = db.get(CampaignTarget, tid)
        assert t.attach_run_count == 1  # 去重：仍计 1
        stat = db.get(CampaignStat, _cid)
        assert stat.attach_cnt == 1
    finally:
        db.close()
