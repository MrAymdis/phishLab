"""冒烟测试：应用可导入、健康检查、OpenAPI、鉴权、核心端点真实数据契约。"""
from fastapi.testclient import TestClient

from app.core.security import create_token
from app.main import app

client = TestClient(app)


def _auth_headers(username: str = "tester") -> dict:
    token = create_token(1, username)
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "up"


def test_openapi_generated():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    # 关键 API 面已挂载
    assert "/api/v1/campaigns" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/ai/chat/stream" in paths
    assert "/openapi/v1/oauth/token" in paths
    assert "/api/v1/emp-users" in paths


def test_unauthenticated_blocked():
    r = client.get("/api/v1/campaigns")
    assert r.status_code == 401
    assert r.json()["code"] == 40101


def test_login_flow():
    r = client.post("/api/v1/auth/login", json={"username": "tester", "password": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["real_name"] == "测试员"

    me = client.get("/api/v1/auth/me", headers=_auth_headers())
    assert me.json()["code"] == 0
    assert me.json()["data"]["username"] == "tester"

    bad = client.post("/api/v1/auth/login", json={"username": "tester", "password": "wrong"})
    assert bad.json()["code"] == 40101


def test_menus():
    r = client.get("/api/v1/auth/menus", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    # 无 license 行 → 演示模式：API 开放平台菜单被 feature 门控，10 项菜单
    assert len(body["data"]) == 10
    assert body["data"][0]["path"] == "/dashboard"


def test_emp_users_empty():
    r = client.get("/api/v1/emp-users", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["list"] == []
    assert body["data"]["total"] == 0
    assert body["data"]["pageSize"] == 20


def test_campaign_dashboard_missing():
    r = client.get("/api/v1/campaigns/1/dashboard", headers=_auth_headers())
    assert r.status_code == 404
    assert r.json()["code"] == 10404


def test_license_status():
    r = client.get("/api/v1/license", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["edition"] == "trial"
    assert "quotas" in body["data"]


def test_settings_get():
    r = client.get("/api/v1/settings", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert isinstance(body["data"], dict)


def test_ai_drafts_empty():
    r = client.get("/api/v1/ai/drafts", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == []


def test_list_endpoints_contract():
    """各列表端点统一返回 code=0（空库下为空结构而非 500/NOT_IMPLEMENTED）。"""
    endpoints = [
        "/api/v1/campaigns", "/api/v1/depts", "/api/v1/email-templates",
        "/api/v1/landing-pages", "/api/v1/attachments", "/api/v1/channels",
        "/api/v1/sender-profiles", "/api/v1/domains", "/api/v1/courses",
        "/api/v1/training-tasks", "/api/v1/exam/questions", "/api/v1/exam/papers",
        "/api/v1/mail-reports", "/api/v1/overview/metrics?range=month",
        "/api/v1/roles", "/api/v1/audit-logs", "/api/v1/login-logs",
        "/api/v1/webhooks", "/api/v1/siem", "/api/v1/ai/sessions",
        "/api/v1/groups", "/api/v1/tags",
    ]
    for path in endpoints:
        r = client.get(path, headers=_auth_headers())
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert r.json()["code"] == 0, f"{path} -> {r.json()}"
    # 旗舰专属功能（开放平台）在演示模式（无 license 行）下路由级 fail-closed 拒绝
    r = client.get("/api/v1/open-apps", headers=_auth_headers())
    assert r.status_code == 403, f"演示模式应拒绝开放平台: {r.status_code}"
    assert r.json()["code"] == 40302
