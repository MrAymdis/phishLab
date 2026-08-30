"""员工批量导出（xlsx + 审计）与顶栏通知（跨演练预警）测试。"""
import datetime
import urllib.parse

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.modules.campaign.models import Campaign, CampaignAlert
from app.modules.org.models import EmpDept, EmpUser
from app.modules.rbac.models import AuditLog

_BASE = 9800

client = TestClient(app)


def _hdr() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"Authorization": "Bearer " + jwt.encode(
        {"sub": "1", "username": "tester", "iat": now,
         "exp": now + datetime.timedelta(minutes=60)},
        settings.secret_key, algorithm="HS256")}


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    db.query(CampaignAlert).filter(CampaignAlert.campaign_id >= _BASE).delete()
    db.query(Campaign).filter(Campaign.id >= _BASE).delete()
    db.query(EmpUser).filter(EmpUser.id >= _BASE).delete()
    db.query(EmpDept).filter(EmpDept.id >= _BASE).delete()
    db.query(AuditLog).filter(AuditLog.action == "export_users").delete()
    db.commit()
    db.close()


# ---------- 员工批量导出 ----------


def test_emp_export_xlsx():
    db = SessionLocal()
    db.add(EmpDept(id=_BASE + 1, name="导出部", path=f"/{_BASE + 1}"))
    db.add(EmpUser(id=_BASE + 1, name="张三", email=f"zhangsan{_BASE}@corp.com",
                   emp_no=f"E{_BASE}1", dept_id=_BASE + 1, status=1))
    db.add(EmpUser(id=_BASE + 2, name="李四", email=f"lisi{_BASE}@corp.com",
                   emp_no=f"E{_BASE}2", dept_id=_BASE + 1, status=1))
    db.commit()
    db.close()

    r = client.post("/api/v1/emp-users/export", json={}, headers=_hdr())
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK", "应为 xlsx（OOXML zip）"
    cd = urllib.parse.unquote(r.headers.get("content-disposition", ""))
    assert "员工档案" in cd and ".xlsx" in cd
    # 导出留审计（红线：所有写操作/导出留痕）
    db = SessionLocal()
    log = db.query(AuditLog).filter(AuditLog.action == "export_users").first()
    assert log is not None and log.account_id == 1
    db.close()


def test_emp_export_dept_filter_ok():
    """按部门筛选导出：不存在的部门返回空表文件而非报错。"""
    db = SessionLocal()
    db.add(EmpDept(id=_BASE + 11, name="A部", path=f"/{_BASE + 11}"))
    db.add(EmpUser(id=_BASE + 21, name="赵六", email=f"zhao{_BASE}@corp.com",
                   dept_id=_BASE + 11, status=1))
    db.commit()
    db.close()

    r = client.post("/api/v1/emp-users/export", json={"dept_id": _BASE + 9999}, headers=_hdr())
    assert r.status_code == 200 and r.content[:2] == b"PK"


# ---------- 顶栏通知（跨演练预警） ----------


def test_alerts_latest():
    db = SessionLocal()
    db.add(Campaign(id=_BASE + 1, name="顶栏演练", type="email", status="running",
                    creator_id=1, auth_confirmed=1, target_mode="manual",
                    schedule_type="immediate"))
    db.add(CampaignAlert(id=_BASE + 1, campaign_id=_BASE + 1, type="pwd_submit",
                         level=3, message="3 名员工提交口令", handled=0))
    db.add(CampaignAlert(id=_BASE + 2, campaign_id=_BASE + 1, type="dept_threshold",
                         level=2, message="财务部中招偏高", handled=1))
    db.add(CampaignAlert(id=_BASE + 3, campaign_id=_BASE + 1, type="wecom_bounce",
                         level=2, message="通道退信（运营类，不入顶栏）", handled=0))
    db.commit()
    db.close()

    r = client.get("/api/v1/alerts/latest", headers=_hdr())
    assert r.status_code == 200 and r.json()["code"] == 0, r.text
    data = r.json()["data"]
    # wecom_bounce 属运营错误，不计入行为类预警/未处置计数
    assert data["unhandled"] == 1
    types = [a["type"] for a in data["list"]]
    assert set(types) == {"pwd_submit", "dept_threshold"}
    first = data["list"][0]
    assert first["campaign_name"] == "顶栏演练" and first["created_at"]
