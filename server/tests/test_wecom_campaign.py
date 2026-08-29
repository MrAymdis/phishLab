"""企业微信演练链路单元测试：员工 userid 管理、social 演练校验/创建/启动、企微模板审核流。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.core.errors import BizError, ErrorCode
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.campaign.models import Campaign, CampaignAlert, CampaignStat, CampaignTarget
from app.modules.campaign.service import (
    _alert_skipped_wecom,
    _require_wecom_auth,
    _resolve_wecom_targets,
    _validate_wecom_campaign,
    create_campaign,
    start,
)
from app.modules.channel.models import SendChannel
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.org.service import create_user, delete_user, list_wecom_candidates, update_user
from app.modules.rbac.models import AuditLog
from app.modules.template.models import WecomTemplate
from app.modules.template.service import (
    create_wecom_template,
    delete_wecom_template,
    set_wecom_template_status,
    update_wecom_template,
)

_BASE = 8600

AUTH_FULL = ["wecom:written_auth", "wecom:domain_verified", "wecom:internal_only"]


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (AuditLog, CampaignAlert, CampaignTarget, CampaignStat, Campaign,
                  WecomTemplate, SendChannel, EmpRiskProfile, EmpUser, EmpDept):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _account(db) -> SysAccount:
    return db.get(SysAccount, 1)


def _emp(db, uid: int, name: str, userid: str | None = None) -> EmpUser:
    db.add(EmpUser(id=uid, name=name, email=f"u{uid}@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid=userid))
    db.commit()
    return db.get(EmpUser, uid)


def _wecom_tpl(db, name="安全演练通知", status="approved", title="{{.FirstName}} 安全演练",
               description="请及时完成安全验证 {{.ResetURL}}") -> WecomTemplate:
    t = WecomTemplate(name=name, msg_type="textcard", title=title, description=description,
                      btn_text="立即处理", url_mode="track", status=status, created_by=1)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _payload(**kw) -> SimpleNamespace:
    """social 演练创建 payload（与 CampaignCreate schema 对齐，只建服务层读到的字段）。"""
    base = dict(
        name="企微钓鱼演练", description="", type="social", template_id=None,
        landing_page_id=None, channel_id=None, sender_profile_id=None,
        track_base_url="", landing_base_url="", target_mode="csv",
        target_snapshot={"user_ids": []},
        schedule_type="immediate", schedule_at=None, ended_at=None,
        batch_count=1, batch_interval_min=0, randomize_content=False, time_jitter_sec=0,
        pixel_degrade=0, training_policy=None, training_redirect_url=None,
        course_ids=[], force_training_rules=[],
        auth_confirmed=True, auth_snapshot=list(AUTH_FULL),
        wecom_template_id=None, attachment_ids=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ---------- 员工 userid 管理 ----------

def test_norm_wecom_userid_unique_and_stripped():
    db = SessionLocal()
    create_user(db, _account(db), {"name": "张三", "email": "u1@corp.com",
                                   "dept_id": 0, "wecom_userid": "  zhangsan  "})
    row = db.scalar(select(EmpUser).where(EmpUser.email == "u1@corp.com"))
    assert row.wecom_userid == "zhangsan"  # 去首尾空白

    with pytest.raises(BizError) as ei:
        create_user(db, _account(db), {"name": "李四", "email": "u2@corp.com",
                                       "dept_id": 0, "wecom_userid": "zhangsan"})
    assert "已存在" in ei.value.message
    db.close()


def test_update_user_wecom_userid_semantics():
    db = SessionLocal()
    uid = create_user(db, _account(db), {"name": "张三", "email": "u1@corp.com",
                                         "dept_id": 0, "wecom_userid": "zhangsan"})
    # None（未传）：保持不变
    update_user(db, _account(db), uid, {"name": "张三", "email": "u1@corp.com",
                                        "dept_id": 0, "initial_risk": 70})
    assert db.get(EmpUser, uid).wecom_userid == "zhangsan"
    # ""：清除
    update_user(db, _account(db), uid, {"name": "张三", "email": "u1@corp.com",
                                        "dept_id": 0, "initial_risk": 70, "wecom_userid": ""})
    assert db.get(EmpUser, uid).wecom_userid is None
    # 清除后他人可复用该 userid
    create_user(db, _account(db), {"name": "李四", "email": "u2@corp.com",
                                   "dept_id": 0, "wecom_userid": "zhangsan"})
    db.close()


def test_list_wecom_candidates_only_active_users_with_userid():
    db = SessionLocal()
    _emp(db, _BASE + 1, "有userid", userid="userA")
    _emp(db, _BASE + 2, "无userid", userid=None)
    _emp(db, _BASE + 3, "空userid", userid="")
    db.add(EmpUser(id=_BASE + 4, name="离职员工", email=f"u{_BASE + 4}@corp.com",
                   dept_id=0, status=0, initial_risk=70, wecom_userid="leftA"))
    db.commit()

    rows = list_wecom_candidates(db, _account(db))
    assert [r["wecom_userid"] for r in rows] == ["userA"]

    rows = list_wecom_candidates(db, _account(db), kw="user")
    assert [r["wecom_userid"] for r in rows] == ["userA"]
    assert list_wecom_candidates(db, _account(db), kw="不存在的") == []
    db.close()


def test_delete_user_releases_wecom_userid_for_readd():
    db = SessionLocal()
    uid = create_user(db, _account(db), {"name": "张三", "email": "u1@corp.com",
                                         "dept_id": 0, "wecom_userid": "zhangsan"})
    delete_user(db, _account(db), uid)
    row = db.get(EmpUser, uid)
    assert row.status == 0 and "zhangsan" in row.wecom_userid and "#del" in row.wecom_userid
    # 重新入职可直接复用原 userid
    new_id = create_user(db, _account(db), {"name": "张三(复职)", "email": "u1@corp.com",
                                            "dept_id": 0, "wecom_userid": "zhangsan"})
    assert db.get(EmpUser, new_id).wecom_userid == "zhangsan"
    db.close()


# ---------- social 演练授权与校验 ----------

def test_require_wecom_auth_rejects_incomplete_snapshot():
    with pytest.raises(BizError) as ei:
        _require_wecom_auth(_payload(auth_snapshot=["wecom:written_auth"]))
    assert "书面授权" not in ei.value.message  # 缺的是后两项
    assert "可信域名" in ei.value.message and "本企业成员" in ei.value.message
    _require_wecom_auth(_payload())  # 完整快照不抛
    _require_wecom_auth(_payload(type="mail", auth_snapshot=[]))  # 非 social 不校验


def test_validate_wecom_campaign_gates():
    db = SessionLocal()
    with pytest.raises(BizError) as ei:
        _validate_wecom_campaign(db, _payload(wecom_template_id=None))
    assert "模板" in ei.value.message

    with pytest.raises(BizError) as ei:
        _validate_wecom_campaign(db, _payload(wecom_template_id=999999))
    assert ei.value.code == ErrorCode.NOT_FOUND

    draft = _wecom_tpl(db, status="draft")
    with pytest.raises(BizError) as ei:
        _validate_wecom_campaign(db, _payload(wecom_template_id=draft.id))
    assert "审核" in ei.value.message

    approved = _wecom_tpl(db, name="已审核模板")
    smtp = SendChannel(name="SMTP", type="smtp", smtp_host="smtp.example.com",
                       smtp_port=587, daily_limit=100)
    db.add(smtp)
    db.commit()
    db.refresh(smtp)
    with pytest.raises(BizError) as ei:
        _validate_wecom_campaign(db, _payload(wecom_template_id=approved.id, channel_id=smtp.id))
    assert "企业微信" in ei.value.message
    _validate_wecom_campaign(db, _payload(wecom_template_id=approved.id))  # 合法配置通过
    db.close()


def test_resolve_wecom_targets_skips_no_userid_and_alerts():
    db = SessionLocal()
    with_uid = _emp(db, _BASE + 1, "有userid", userid="userA")
    without = _emp(db, _BASE + 2, "无userid", userid=None)
    _emp(db, _BASE + 3, "无userid2", userid="")

    ids, skipped = _resolve_wecom_targets(
        db, "csv", {"user_ids": [with_uid.id, without.id, _BASE + 3]})
    assert ids == [with_uid.id]
    assert {u.id for u in skipped} == {without.id, _BASE + 3}

    # 告警落库（>5 人截断文案）
    db.add(Campaign(id=_BASE + 1, name="告警演练", type="social", status="draft",
                    creator_id=1, auth_confirmed=1, target_mode="manual",
                    schedule_type="immediate"))
    db.commit()
    _alert_skipped_wecom(db, _BASE + 1, skipped)
    db.commit()
    alert = db.scalar(select(CampaignAlert).where(
        CampaignAlert.campaign_id == _BASE + 1, CampaignAlert.type == "wecom_no_userid"))
    assert alert is not None and "2 名" in alert.message
    db.close()


def test_create_social_campaign_expands_targets_and_persists_auth():
    db = SessionLocal()
    tpl = _wecom_tpl(db)
    with_uid = _emp(db, _BASE + 1, "有userid", userid="userA")
    _emp(db, _BASE + 2, "无userid", userid=None)

    cid = create_campaign(db, _account(db), _payload(
        wecom_template_id=tpl.id, target_snapshot={"user_ids": [with_uid.id, _BASE + 2]}))
    c = db.get(Campaign, cid)
    assert c.type == "social" and c.target_count == 1
    assert c.auth_confirmed == 1 and c.auth_snapshot == AUTH_FULL
    assert c.wecom_template_id == tpl.id
    targets = db.scalars(select(CampaignTarget).where(CampaignTarget.campaign_id == cid)).all()
    assert len(targets) == 1 and targets[0].user_id == with_uid.id and len(targets[0].token) == 32
    alert = db.scalar(select(CampaignAlert).where(
        CampaignAlert.campaign_id == cid, CampaignAlert.type == "wecom_no_userid"))
    assert alert is not None  # 被跳过员工即时告警
    db.close()


def test_create_social_campaign_rejects_when_all_targets_lack_userid():
    db = SessionLocal()
    tpl = _wecom_tpl(db)
    no_uid = _emp(db, _BASE + 2, "无userid", userid=None)
    with pytest.raises(BizError) as ei:
        create_campaign(db, _account(db), _payload(
            wecom_template_id=tpl.id, target_snapshot={"user_ids": [no_uid.id]}))
    assert "userid" in ei.value.message
    db.close()


def test_create_campaign_requires_auth_confirmed():
    db = SessionLocal()
    tpl = _wecom_tpl(db)
    _emp(db, _BASE + 1, "有userid", userid="userA")
    with pytest.raises(BizError) as ei:
        create_campaign(db, _account(db), _payload(
            wecom_template_id=tpl.id, target_snapshot={"user_ids": [_BASE + 1]},
            auth_confirmed=False))
    assert "授权" in ei.value.message
    db.close()


def test_start_social_requires_wecom_channel():
    db = SessionLocal()
    tpl = _wecom_tpl(db)
    _emp(db, _BASE + 1, "有userid", userid="userA")
    cid = create_campaign(db, _account(db), _payload(
        wecom_template_id=tpl.id, target_snapshot={"user_ids": [_BASE + 1]}))
    with pytest.raises(BizError) as ei:
        start(db, _account(db), cid)
    assert "企业微信发送通道" in ei.value.message
    assert db.get(Campaign, cid).status == "draft"  # 校验失败不落 sending 悬挂态
    db.close()


def test_start_social_rejects_incomplete_auth_snapshot():
    db = SessionLocal()
    # 直接构造 auth_snapshot 不完整的草稿（绕过 create 校验，模拟历史脏数据）
    db.add(Campaign(id=_BASE + 1, name="脏数据演练", type="social", status="draft",
                    creator_id=1, auth_confirmed=1, target_mode="manual",
                    schedule_type="immediate", auth_snapshot=[]))
    db.commit()
    with pytest.raises(BizError) as ei:
        start(db, _account(db), _BASE + 1)
    assert "授权条款不完整" in ei.value.message
    db.close()


# ---------- 企微消息模板：合规 + 审核流 ----------

def test_wecom_template_banned_words_rejected():
    db = SessionLocal()
    for field in ("title", "description"):
        payload = {"name": "违规模板", "title": "演练通知", "description": "完成验证"}
        payload[field] = f"{payload[field]}【微信安全中心】"
        with pytest.raises(BizError) as ei:
            create_wecom_template(db, _account(db), payload)
        assert "官方" in ei.value.message  # 红线：禁用冒充官方字样
    db.close()


def test_wecom_template_approve_requires_title_and_description():
    db = SessionLocal()
    tid = create_wecom_template(db, _account(db), {"name": "空壳模板"})
    with pytest.raises(BizError) as ei:
        set_wecom_template_status(db, _account(db), tid, "approved")
    assert "标题" in ei.value.message

    update_wecom_template(db, _account(db), tid, {
        "title": "{{.FirstName}} 安全演练", "description": "请点击 {{.ResetURL}}"})
    set_wecom_template_status(db, _account(db), tid, "approved")
    assert db.get(WecomTemplate, tid).status == "approved"

    with pytest.raises(BizError):
        set_wecom_template_status(db, _account(db), tid, "weird")  # 仅 approved/discarded
    db.close()


def test_wecom_template_edit_reverts_approved_to_draft():
    db = SessionLocal()
    tid = create_wecom_template(db, _account(db), {
        "name": "审核后改动", "title": "标题A", "description": "摘要A"})
    set_wecom_template_status(db, _account(db), tid, "approved")
    update_wecom_template(db, _account(db), tid, {"description": "摘要B"})
    assert db.get(WecomTemplate, tid).status == "draft"  # 防误投：需重新审核
    db.close()


def test_wecom_template_update_payload_status_is_ignored():
    """编辑载荷携带 status 不得流转审核状态（绕过审核门的回归防线）。"""
    db = SessionLocal()
    tid = create_wecom_template(db, _account(db), {
        "name": "载荷夹带", "title": "标题A", "description": "摘要A"})
    set_wecom_template_status(db, _account(db), tid, "approved")
    # 前端旧载荷曾带 status: form.status——现在必须被忽略，
    # 内容改动后回到 draft，且不得被夹带值改回 approved/discarded
    update_wecom_template(db, _account(db), tid,
                          {"description": "摘要B", "status": "approved"})
    assert db.get(WecomTemplate, tid).status == "draft"
    # 即便无内容改动，夹带 status 也不能流转状态
    update_wecom_template(db, _account(db), tid, {"status": "discarded"})
    assert db.get(WecomTemplate, tid).status == "draft"
    # 唯一合法流转：review 端点（带审计）
    set_wecom_template_status(db, _account(db), tid, "approved")
    assert db.get(WecomTemplate, tid).status == "approved"
    db.close()


def test_wecom_template_delete_blocked_when_referenced():
    db = SessionLocal()
    tpl = _wecom_tpl(db)
    _emp(db, _BASE + 1, "有userid", userid="userA")
    cid = create_campaign(db, _account(db), _payload(
        wecom_template_id=tpl.id, target_snapshot={"user_ids": [_BASE + 1]}))

    with pytest.raises(BizError) as ei:
        delete_wecom_template(db, _account(db), tpl.id)
    assert "引用" in ei.value.message
    assert db.get(Campaign, cid).wecom_template_id == tpl.id  # 演练引用不受影响
    db.close()
