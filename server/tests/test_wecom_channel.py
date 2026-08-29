"""企业微信通道单元测试：errcode 映射、Secret 加密入库/掩码回显、access_token 缓存、试发路径。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.core.errors import BizError
from app.core.security import decrypt_secret, encrypt_secret
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.channel.models import SendChannel
from app.modules.channel.service import (
    _channel_kw_from_payload,
    _wecom_probe,
    create_channel,
    get_wecom_access_token,
    invalidate_wecom_token,
    list_channels,
    send_wecom_message,
    update_channel,
    wecom_send_status,
)
# 别名导入：避免 pytest 将服务层 test_* 函数误收集为测试用例
from app.modules.channel import service as channel_service
from app.modules.org.models import EmpUser
from app.modules.rbac.models import AuditLog
from app.modules.template.models import WecomTemplate

SECRET = "corp-secret-9f8e7d"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (AuditLog, WecomTemplate, SendChannel, EmpUser):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _account(db) -> SysAccount:
    return db.get(SysAccount, 1)


# ---------- errcode 映射（纯函数） ----------

def test_wecom_send_status_errcode_mapping():
    assert wecom_send_status({"errcode": 0, "errmsg": "ok"}) == ("sent", "", "sent")
    assert wecom_send_status({"errcode": 40014, "errmsg": "invalid"})[2] == "refresh"
    assert wecom_send_status({"errcode": 42001, "errmsg": "expired"})[2] == "refresh"
    assert wecom_send_status({"errcode": 45009, "errmsg": "freq"})[2] == "backoff"
    assert wecom_send_status({"errcode": 45024, "errmsg": "freq"})[2] == "backoff"
    assert wecom_send_status({"errcode": 60111, "errmsg": "no user"})[0] == "bounced"
    assert wecom_send_status({"errcode": 60011, "errmsg": "no perm"})[0] == "failed"
    # 未知 errcode 一律 failed 告警（不静默吞掉）
    status, reason, action = wecom_send_status({"errcode": 99999, "errmsg": "boom"})
    assert (status, action) == ("failed", "fail")
    assert "99999" in reason and "boom" in reason
    # 原因与 errmsg 拼接
    _, reason, _ = wecom_send_status({"errcode": 40014, "errmsg": "invalid"})
    assert "access_token 失效" in reason and "invalid" in reason


# ---------- 通道 CRUD：红线 2 加密入库 + 掩码回显 ----------

def _gettoken_ok(url, params=None, timeout=None):
    assert "gettoken" in str(url)
    assert params["corpid"] == "ww123"
    return SimpleNamespace(json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200})


def test_channel_kw_encrypts_secret_and_strifies_agent_id():
    kw = _channel_kw_from_payload({
        "name": "企微应用", "type": "wecom", "daily_limit": 200,
        "config": {"wecom_corp_id": "ww123", "wecom_agent_id": 1000002,
                   "wecom_secret": SECRET, "wecom_app_name": "演练助手"},
    })
    assert kw["wecom_agent_id"] == "1000002"
    assert kw["wecom_secret_enc"] != SECRET  # 明文绝不落盘
    assert decrypt_secret(kw["wecom_secret_enc"]) == SECRET
    assert "wecom_secret" not in kw  # 明文键不进入模型列


def test_create_and_list_wecom_channel_masks_secret(monkeypatch):
    monkeypatch.setattr("httpx.get", _gettoken_ok)
    db = SessionLocal()
    cid = create_channel(db, _account(db), {
        "name": "企微通道A", "type": "wecom", "daily_limit": 100,
        "config": {"wecom_corp_id": "ww123", "wecom_agent_id": 1000002,
                   "wecom_secret": SECRET, "wecom_app_name": "演练助手"},
    })
    row = db.get(SendChannel, cid)
    assert row.status == "normal"
    assert decrypt_secret(row.wecom_secret_enc) == SECRET

    listed = list_channels(db, _account(db))
    assert len(listed) == 1
    item = listed[0]
    assert item["type"] == "wecom" and item["wecom_corp_id"] == "ww123"
    assert item["wecom_agent_id"] == "1000002" and item["wecom_app_name"] == "演练助手"
    assert item["has_wecom_secret"] is True
    dumped = str(item).lower()
    assert SECRET not in dumped  # API 只回显掩码，Secret 值不回显
    db.close()


def test_update_channel_keeps_existing_secret_when_omitted(monkeypatch):
    monkeypatch.setattr("httpx.get", _gettoken_ok)
    db = SessionLocal()
    cid = create_channel(db, _account(db), {
        "name": "企微通道A", "type": "wecom",
        "config": {"wecom_corp_id": "ww123", "wecom_agent_id": 1000002, "wecom_secret": SECRET},
    })
    before = db.get(SendChannel, cid).wecom_secret_enc
    # 编辑只改名称，config 不带 secret（或空串）：沿用已有密文，不覆盖
    update_channel(db, _account(db), cid, {
        "name": "企微通道B", "type": "wecom", "daily_limit": 50,
        "config": {"wecom_corp_id": "ww123", "wecom_agent_id": 1000002, "wecom_secret": ""},
    })
    row = db.get(SendChannel, cid)
    assert row.name == "企微通道B" and row.daily_limit == 50
    assert row.wecom_secret_enc == before
    assert decrypt_secret(row.wecom_secret_enc) == SECRET
    db.close()


def test_wecom_probe_missing_credentials_abnormal():
    result, status = _wecom_probe({})
    assert status == "abnormal" and result["ok"] is False
    assert "未配置" in result["message"]


# ---------- access_token 缓存 ----------

class _FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, k):
        return self.store.get(k)

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.store:
            return False
        self.store[k] = v
        return True

    def delete(self, k):
        self.store.pop(k, None)


def _wecom_channel(db, **kw) -> SendChannel:
    kw.setdefault("wecom_secret_enc", encrypt_secret(SECRET))
    kw.setdefault("wecom_agent_id", "1000002")
    ch = SendChannel(name="企微通道", type="wecom", wecom_corp_id="ww123",
                     daily_limit=100, status="normal", **kw)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def test_access_token_cached_and_invalidated(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)
    calls = {"n": 0}

    def _get(url, params=None, timeout=None):
        assert "gettoken" in str(url)
        calls["n"] += 1
        return SimpleNamespace(json=lambda: {"errcode": 0, "access_token": "tok-cached", "expires_in": 7200})

    monkeypatch.setattr("httpx.get", _get)
    db = SessionLocal()
    ch = _wecom_channel(db)
    assert get_wecom_access_token(db, ch) == "tok-cached"
    assert get_wecom_access_token(db, ch) == "tok-cached"
    assert calls["n"] == 1  # 第二次走缓存，不调 gettoken

    invalidate_wecom_token(ch)
    assert get_wecom_access_token(db, ch) == "tok-cached"
    assert calls["n"] == 2  # 失效后重新拉取
    db.close()


def test_access_token_gettoken_error_raises(monkeypatch):
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 40013, "errmsg": "invalid corpid"}))
    db = SessionLocal()
    ch = _wecom_channel(db)
    with pytest.raises(BizError) as ei:
        get_wecom_access_token(db, ch)
    assert "40013" in ei.value.message
    db.close()


def test_send_wecom_message_requires_agent_id(monkeypatch):
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    db = SessionLocal()
    ch = _wecom_channel(db, wecom_agent_id=None)
    with pytest.raises(BizError) as ei:
        send_wecom_message(db, ch, "u1", {"msgtype": "textcard", "title": "t"})
    assert "AgentId" in ei.value.message
    db.close()


# ---------- 通道试发 test_wecom ----------

def test_test_wecom_rejects_wrong_channel_type(monkeypatch):
    db = SessionLocal()
    ch = _wecom_channel(db)
    db.execute(delete(SendChannel).where(SendChannel.id != ch.id))
    smtp = SendChannel(name="SMTP通道", type="smtp", smtp_host="smtp.example.com",
                       smtp_port=587, daily_limit=100)
    db.add(smtp)
    db.commit()
    db.refresh(smtp)
    with pytest.raises(BizError) as ei:
        channel_service.test_wecom(db, _account(db), smtp.id)
    assert "仅企业微信" in ei.value.message
    db.close()


def test_test_wecom_rejects_admin_without_emp_binding():
    db = SessionLocal()
    ch = _wecom_channel(db)
    # 测试账号未绑定员工档案
    account = _account(db)
    account.emp_user_id = None
    db.commit()
    with pytest.raises(BizError) as ei:
        channel_service.test_wecom(db, account, ch.id)
    assert "未绑定员工档案" in ei.value.message
    db.close()


def test_test_wecom_rejects_missing_template(monkeypatch):
    db = SessionLocal()
    ch = _wecom_channel(db)
    account = _account(db)
    account.emp_user_id = 90001
    db.add(EmpUser(id=90001, name="管理员", email="admin90001@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="admin01"))
    db.commit()
    with pytest.raises(BizError):
        channel_service.test_wecom(db, account, ch.id, wecom_template_id=999999)
    db.close()


def test_test_wecom_with_to_userid_resolves_employee(monkeypatch):
    """账号未绑定员工档案时，指定 to_userid（在职且已配置 userid）同样可试发。"""
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    sent = {}
    monkeypatch.setattr("httpx.post", lambda url, params=None, json=None, timeout=None: (
        sent.update(touser=json["touser"]) or
        SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok"})))
    db = SessionLocal()
    ch = _wecom_channel(db)
    account = _account(db)
    account.emp_user_id = None  # 未绑定
    db.add(EmpUser(id=90002, name="接收员工", email="r90002@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="receiver01"))
    db.commit()

    result = channel_service.test_wecom(db, account, ch.id, to_userid="receiver01")
    assert result["ok"] is True
    assert sent["touser"] == "receiver01"
    db.close()


def test_test_wecom_to_userid_not_found_rejected():
    db = SessionLocal()
    ch = _wecom_channel(db)
    with pytest.raises(BizError) as ei:
        channel_service.test_wecom(db, _account(db), ch.id, to_userid="ghost")
    assert "不存在" in ei.value.message and "ghost" in ei.value.message
    # 已离职员工（wecom_userid 被 #del 后缀改写/status=0）同样拒绝——红线8 仅在职员工
    db.add(EmpUser(id=90003, name="离职员工", email="left90003@corp.com",
                   dept_id=0, status=0, initial_risk=70, wecom_userid="left01"))
    db.commit()
    with pytest.raises(BizError):
        channel_service.test_wecom(db, _account(db), ch.id, to_userid="left01")
    db.close()


def test_test_wecom_success_writes_result(monkeypatch):
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())

    def _get(url, params=None, timeout=None):
        return SimpleNamespace(json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200})

    sent = {}

    def _post(url, params=None, json=None, timeout=None):
        assert "message/send" in str(url)
        assert params["access_token"] == "tok-1"
        assert json["touser"] == "admin01" and json["agentid"] == 1000002
        assert json["msgtype"] == "textcard" and json["textcard"]["title"] == "PhishLab 通道测试"
        sent["called"] = True
        return SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr("httpx.get", _get)
    monkeypatch.setattr("httpx.post", _post)
    db = SessionLocal()
    ch = _wecom_channel(db)
    account = _account(db)
    account.emp_user_id = 90001
    db.add(EmpUser(id=90001, name="管理员", email="admin90001@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="admin01"))
    db.commit()

    result = channel_service.test_wecom(db, account, ch.id)
    assert sent["called"]
    assert result["ok"] is True and "成功" in result["message"]
    row = db.get(SendChannel, ch.id)
    assert row.last_test_result["ok"] is True
    assert row.last_test_at is not None
    db.close()


def test_test_wecom_text_template_builds_content(monkeypatch):
    """msg_type=text 的模板：标题+摘要拼入 content，避免企微渲染空白气泡。"""
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    sent = {}

    def _post(url, params=None, json=None, timeout=None):
        sent.update(body=json)
        return SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr("httpx.post", _post)
    db = SessionLocal()
    ch = _wecom_channel(db)
    db.add(WecomTemplate(name="文本模板", msg_type="text",
                         title="演练通知", description="请及时查看", status="approved", created_by=1))
    db.commit()
    tpl = db.scalar(select(WecomTemplate))
    db.add(EmpUser(id=90004, name="接收员工", email="r90004@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="textuser"))
    db.commit()

    result = channel_service.test_wecom(db, _account(db), ch.id,
                                        wecom_template_id=tpl.id, to_userid="textuser")
    assert result["ok"] is True
    assert sent["body"]["msgtype"] == "text"
    assert sent["body"]["text"]["content"] == "演练通知\n请及时查看"
    db.close()


def test_test_wecom_text_template_empty_fields_content_fallback(monkeypatch):
    """text 模板标题/摘要为空时 content 兜底非空。"""
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    sent = {}
    monkeypatch.setattr("httpx.post", lambda url, params=None, json=None, timeout=None: (
        sent.update(body=json) or
        SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok"})))
    db = SessionLocal()
    ch = _wecom_channel(db)
    db.add(WecomTemplate(name="空壳文本模板", msg_type="text",
                         title=None, description=None, status="approved", created_by=1))
    db.commit()
    tpl = db.scalar(select(WecomTemplate))
    db.add(EmpUser(id=90005, name="接收员工", email="r90005@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="textuser2"))
    db.commit()

    result = channel_service.test_wecom(db, _account(db), ch.id,
                                        wecom_template_id=tpl.id, to_userid="textuser2")
    assert result["ok"] is True
    assert (sent["body"]["text"]["content"] or "").strip() != ""
    db.close()


def test_test_wecom_invaliduser_reports_failure(monkeypatch):
    """errcode=0 但 invaliduser 含目标：企微实际未送达，不得报试发成功。"""
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    monkeypatch.setattr("httpx.post", lambda url, params=None, json=None, timeout=None: (
        SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok",
                                      "invaliduser": "admin01|other"})))
    db = SessionLocal()
    ch = _wecom_channel(db)
    account = _account(db)
    account.emp_user_id = 90001
    db.add(EmpUser(id=90001, name="管理员", email="admin90001@corp.com",
                   dept_id=0, status=1, initial_risk=70, wecom_userid="admin01"))
    db.commit()

    result = channel_service.test_wecom(db, account, ch.id)
    assert result["ok"] is False
    assert "invaliduser" in result["message"] and "admin01" in result["message"]
    assert db.get(SendChannel, ch.id).last_test_result["ok"] is False
    db.close()


def test_send_wecom_message_text_without_content_falls_back(monkeypatch):
    """send 层防御：text 消息缺 content 时用 title/description 兜底，杜绝空白气泡。"""
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(
        "httpx.get", lambda url, params=None, timeout=None: SimpleNamespace(
            json=lambda: {"errcode": 0, "access_token": "tok-1", "expires_in": 7200}))
    sent = {}
    monkeypatch.setattr("httpx.post", lambda url, params=None, json=None, timeout=None: (
        sent.update(body=json) or
        SimpleNamespace(json=lambda: {"errcode": 0, "errmsg": "ok"})))
    db = SessionLocal()
    ch = _wecom_channel(db)

    send_wecom_message(db, ch, "someone",
                       {"msgtype": "text", "title": "仅标题", "description": ""})
    assert sent["body"]["msgtype"] == "text"
    assert sent["body"]["text"]["content"] == "仅标题"
    db.close()
