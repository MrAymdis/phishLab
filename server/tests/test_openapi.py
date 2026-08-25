"""开放平台业务 API 测试：网关鉴权（JWT/应用状态/IP白名单/scope/限流）+ 业务端点 + 调用审计。

HTTP 层走 TestClient 真实路由；限流依赖 mock Redis（真实 Redis 不在测试环境）。
口径校验：中招 = 提交 + 附件运行（与内部报表一致）。
"""
import datetime

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.modules.campaign.models import Campaign, CampaignStat, CampaignTarget
from app.modules.openapi_mod import service
from app.modules.openapi_mod.models import OpenApiLog, OpenApp
from app.modules.org.models import EmpDept, EmpUser
from app.modules.report.models import MailReport
from app.modules.template.models import EmailTemplate
from app.modules.tracking.models import TrackEvent

_BASE = 9200
_APP_ID = f"app_test{_BASE}"

client = TestClient(app)


def _token(app_id: str = _APP_ID, scopes: list[str] | None = None,
           exp_minutes: int = 120) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode(
        {"sub": f"app:{app_id}", "scopes": scopes or ["campaign"], "iat": now,
         "exp": now + datetime.timedelta(minutes=exp_minutes)},
        settings.secret_key, algorithm="HS256",
    )


def _hdr(scopes: list[str] | None = None) -> dict:
    return {"Authorization": f"Bearer {_token(scopes=scopes)}"}


@pytest.fixture()
def seed():
    db = SessionLocal()
    db.add(EmpDept(id=_BASE + 1, parent_id=0, path=f"/{_BASE + 1}", name="开放平台部"))
    db.add(EmpUser(id=_BASE + 1, name="开放员工", email=f"open{_BASE}@corp.com",
                   dept_id=_BASE + 1, status=1))
    db.add(Campaign(id=_BASE + 1, name="开放平台演练", type="email", status="completed",
                    creator_id=1, auth_confirmed=1, target_mode="manual", schedule_type="immediate"))
    db.add(CampaignStat(campaign_id=_BASE + 1, delivered_cnt=1, open_cnt=1,
                        click_cnt=1, submit_cnt=1))
    db.add(CampaignTarget(id=_BASE + 1, campaign_id=_BASE + 1, user_id=_BASE + 1, batch_no=1,
                          token=f"tk{_BASE}", send_status="delivered", submit_flag=1,
                          open_count=1, click_count=1))
    db.add(TrackEvent(id=_BASE + 1, campaign_id=_BASE + 1, user_id=_BASE + 1, event_type="submit"))
    db.add(TrackEvent(id=_BASE + 2, campaign_id=_BASE + 1, user_id=_BASE + 1, event_type="open"))
    db.add(MailReport(id=_BASE + 1, channel="manual", reporter_user_id=_BASE + 1,
                      reporter_email=f"open{_BASE}@corp.com", subject="开放测试举报",
                      classification="drill"))
    db.add(EmailTemplate(id=_BASE + 1, name="开放模板", scene="finance", subject="开放测试",
                         html_body="<p>开放模板正文</p>"))
    db.add(OpenApp(id=_BASE + 1, app_id=_APP_ID, app_secret_enc=b"\x00" * 16,
                   name="测试应用", scopes=["campaign", "report", "user", "template",
                                         "mail_report", "system"],
                   ip_whitelist=[], rate_limit=60, status="active", created_by=1))
    db.commit()
    yield db
    db.execute(OpenApiLog.__table__.delete().where(OpenApiLog.app_id == _APP_ID))
    db.query(TrackEvent).filter(TrackEvent.id >= _BASE).delete()
    db.query(MailReport).filter(MailReport.id >= _BASE).delete()
    db.query(EmailTemplate).filter(EmailTemplate.id >= _BASE).delete()
    db.query(CampaignTarget).filter(CampaignTarget.campaign_id >= _BASE).delete()
    db.query(CampaignStat).filter(CampaignStat.campaign_id >= _BASE).delete()
    db.query(Campaign).filter(Campaign.id >= _BASE).delete()
    db.query(EmpUser).filter(EmpUser.id >= _BASE).delete()
    db.query(EmpDept).filter(EmpDept.id >= _BASE).delete()
    db.query(OpenApp).filter(OpenApp.id >= _BASE).delete()
    db.commit()
    db.close()


# ---------- 网关鉴权 ----------


def test_gateway_requires_token(seed):
    r = client.get("/openapi/v1/campaigns")
    assert r.status_code == 401 and r.json()["code"] == 40101


def test_gateway_rejects_bad_token(seed):
    r = client.get("/openapi/v1/campaigns", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401


def test_gateway_rejects_expired_token(seed):
    hdr = {"Authorization": f"Bearer {_token(exp_minutes=-1)}"}
    r = client.get("/openapi/v1/campaigns", headers=hdr)
    assert r.status_code == 401 and r.json()["code"] == 40102


def test_gateway_scope_denied(seed):
    r = client.get("/openapi/v1/campaigns", headers=_hdr(scopes=["report"]))
    assert r.status_code == 403 and r.json()["code"] == 40302


def test_gateway_rejects_disabled_app(seed):
    app_row = seed.get(OpenApp, _BASE + 1)
    app_row.status = "disabled"
    seed.commit()
    r = client.get("/openapi/v1/campaigns", headers=_hdr())
    assert r.status_code == 403


def test_gateway_ip_whitelist(seed):
    app_row = seed.get(OpenApp, _BASE + 1)
    app_row.ip_whitelist = ["10.1.2.3"]
    seed.commit()
    r = client.get("/openapi/v1/campaigns", headers=_hdr())
    assert r.status_code == 403 and "白名单" in r.json()["message"]


def test_gateway_rate_limit(seed, monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.n = 0

        def incr(self, key):  # noqa: ARG002
            self.n += 1
            return self.n

        def expire(self, key, ttl):  # noqa: ARG002
            pass

    fake = FakeRedis()
    monkeypatch.setattr(service, "_redis", lambda: fake)  # 单例：跨调用共享计数
    app_row = seed.get(OpenApp, _BASE + 1)
    app_row.rate_limit = 1
    seed.commit()
    assert client.get("/openapi/v1/campaigns", headers=_hdr()).status_code == 200
    r = client.get("/openapi/v1/campaigns", headers=_hdr())
    assert r.status_code == 429 and r.json()["code"] == 42902


# ---------- campaign scope ----------


def test_campaign_list_and_detail(seed):
    h = _hdr()
    r = client.get("/openapi/v1/campaigns", headers=h)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 1
    item = data["list"][0]
    assert item["name"] == "开放平台演练"
    assert item["stats"]["submit"] == 1 and item["stats"]["attach"] == 0

    r2 = client.get(f"/openapi/v1/campaigns/{_BASE + 1}", headers=h)
    d2 = r2.json()["data"]
    assert d2["victim_count"] == 1 and d2["stats"]["open"] == 1


def test_campaign_targets_and_report(seed):
    h = _hdr()
    r = client.get(f"/openapi/v1/campaigns/{_BASE + 1}/targets", headers=h)
    t = r.json()["data"]["list"][0]
    assert t["victim"] is True and t["name"] == "开放员工" and t["dept"] == "开放平台部"

    r2 = client.get(f"/openapi/v1/campaigns/{_BASE + 1}/targets?victim_only=true", headers=h)
    assert r2.json()["data"]["total"] == 1

    r3 = client.get(f"/openapi/v1/campaigns/{_BASE + 1}/report", headers=h)
    rep = r3.json()["data"]
    assert rep["metrics"][3]["value"] == 1  # 中招数（submit=1 + attach=0）
    assert rep["funnel"][3]["stage"] == "中招"
    assert rep["victims_top"][0]["submit"] is True
    assert rep["daily"]["labels"]


def test_campaign_404(seed):
    r = client.get("/openapi/v1/campaigns/999999", headers=_hdr())
    assert r.status_code == 404


def test_create_campaign_requires_auth_confirmed(seed):
    payload = {
        "name": "API 演练", "type": "mail", "target_mode": "dept",
        "target_snapshot": {"dept_ids": [_BASE + 1]},
        "schedule_type": "now", "auth_confirmed": False,
    }
    r = client.post("/openapi/v1/campaigns", json=payload, headers=_hdr())
    assert r.json()["code"] == 10001 and "授权" in r.json()["message"]


def test_create_campaign_success_as_draft(seed):
    payload = {
        "name": "API 演练", "type": "mail", "target_mode": "dept",
        "target_snapshot": {"dept_ids": [_BASE + 1]},
        "schedule_type": "now", "auth_confirmed": True,
    }
    r = client.post("/openapi/v1/campaigns", json=payload, headers=_hdr())
    assert r.json()["code"] == 0
    cid = r.json()["data"]["id"]
    d = client.get(f"/openapi/v1/campaigns/{cid}", headers=_hdr()).json()["data"]
    assert d["status"] == "draft" and d["target_count"] == 1  # 红线 4：产物为草稿，启动在平台内


# ---------- report / user / template / mail_report / system scope ----------


def test_report_endpoints(seed):
    h = _hdr(scopes=["report"])
    r = client.get("/openapi/v1/reports/overview", headers=h)
    d = r.json()["data"]
    assert d["campaign_total"] >= 1 and d["victim_total"] >= 1

    r2 = client.get("/openapi/v1/reports/trend?range=month", headers=h)
    assert "labels" in r2.json()["data"] and "victim" in r2.json()["data"]

    r3 = client.get("/openapi/v1/reports/department", headers=h)
    rows = r3.json()["data"]["rows"]
    assert rows and rows[0]["dept"] == "开放平台部" and rows[0]["victim"] == 1


def test_user_endpoints(seed):
    h = _hdr(scopes=["user"])
    r = client.get("/openapi/v1/users", headers=h)
    u = r.json()["data"]["list"][0]
    assert u["name"] == "开放员工" and u["behavior"]["victim"] == 1

    r2 = client.get(f"/openapi/v1/users/{_BASE + 1}", headers=h)
    d2 = r2.json()["data"]
    assert d2["behavior"]["open"] >= 1 and d2["recent_events"][0]["event_type"] == "open"


def test_template_mail_report_system_endpoints(seed):
    h = _hdr(scopes=["template"])
    r = client.get("/openapi/v1/templates", headers=h)
    assert r.json()["data"]["list"][0]["name"] == "开放模板"
    r2 = client.get(f"/openapi/v1/templates/{_BASE + 1}", headers=h)
    assert "开放模板正文" in r2.json()["data"]["html_body"]

    r3 = client.get("/openapi/v1/mail-reports", headers=_hdr(scopes=["mail_report"]))
    rep = r3.json()["data"]["list"][0]
    assert rep["classification"] == "drill" and rep["subject"] == "开放测试举报"

    r4 = client.get("/openapi/v1/system/info", headers=_hdr(scopes=["system"]))
    assert r4.json()["data"]["emp_total"] >= 1


# ---------- 调用审计 ----------


def test_calls_logged(seed):
    client.get("/openapi/v1/campaigns", headers=_hdr())
    client.get("/openapi/v1/campaigns/999999", headers=_hdr())  # 404 也留痕
    db = seed
    logs = db.query(OpenApiLog).filter(OpenApiLog.app_id == _APP_ID).order_by(OpenApiLog.id).all()
    assert len(logs) == 2
    assert logs[0].path == "/openapi/v1/campaigns" and logs[0].status_code == 200
    assert logs[1].status_code == 404 and logs[1].error_msg
