"""删除演练的数据一致性测试：级联清除 TrackEvent 并重算员工画像。

档案"历史中招"（emp_risk_profile.phish_count）与轨迹均以 track_event 为源，
演练删除后必须同步，否则"活动删了档案仍有中招数据"。
"""
from datetime import datetime

from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.campaign.service import delete_campaign
from app.modules.org.models import EmpRiskProfile, EmpUser
from app.modules.tracking.models import TrackEvent

_BASE = 9600


def _seed():
    db = SessionLocal()
    db.add(EmpUser(id=_BASE + 1, name="删除测试", email=f"del{_BASE}@corp.com",
                   dept_id=0, status=1, initial_risk=70))
    db.add(EmpRiskProfile(user_id=_BASE + 1, total_score=75, risk_level=2, phish_count=3))
    db.add(Campaign(id=_BASE + 1, name="待删演练", type="email", status="terminated",
                    creator_id=1, auth_confirmed=1, target_mode="manual", schedule_type="immediate"))
    db.add(CampaignTarget(id=_BASE + 100, campaign_id=_BASE + 1, user_id=_BASE + 1,
                          batch_no=1, token="deltk", send_status="sent",
                          sent_at=datetime(2026, 8, 20, 10, 0, 0),
                          submit_flag=1, attach_run_count=0))
    db.commit()
    db.close()


def _cleanup():
    db = SessionLocal()
    db.query(TrackEvent).filter(TrackEvent.campaign_id == _BASE + 1).delete()
    db.query(CampaignTarget).filter(CampaignTarget.id == _BASE + 100).delete()
    db.query(Campaign).filter(Campaign.id == _BASE + 1).delete()
    db.query(EmpRiskProfile).filter(EmpRiskProfile.user_id == _BASE + 1).delete()
    db.query(EmpUser).filter(EmpUser.id == _BASE + 1).delete()
    db.commit()
    db.close()


def test_delete_campaign_cleans_track_events_and_recalcs_profile():
    _seed()
    try:
        db = SessionLocal()
        # 演练产生过 2 次 submit + 1 次 attach_run（3 次中招事件）
        db.add(TrackEvent(campaign_id=_BASE + 1, user_id=_BASE + 1, token="deltk",
                          event_type="submit", created_at=datetime(2026, 8, 21, 10, 0, 0)))
        db.add(TrackEvent(campaign_id=_BASE + 1, user_id=_BASE + 1, token="deltk",
                          event_type="submit", created_at=datetime(2026, 8, 21, 11, 0, 0)))
        db.add(TrackEvent(campaign_id=_BASE + 1, user_id=_BASE + 1, token="deltk",
                          event_type="attach_run", created_at=datetime(2026, 8, 21, 12, 0, 0)))
        db.commit()

        account = db.get(SysAccount, 1)
        delete_campaign(db, account, _BASE + 1)
        db.expire_all()

        # 1) 追踪事件已级联清除
        remain = db.query(TrackEvent).filter(TrackEvent.campaign_id == _BASE + 1).count()
        assert remain == 0
        # 2) 画像快照已重算：无剩余事件 → 中招 0，综合分回落到初始风险
        profile = db.get(EmpRiskProfile, _BASE + 1)
        assert profile.phish_count == 0, "删除演练后档案不应残留历史中招次数"
        assert profile.risk_level == 1  # 70 分初始 → 低风险
        # 3) 演练本身已删
        assert db.get(Campaign, _BASE + 1) is None
        db.close()
    finally:
        _cleanup()
