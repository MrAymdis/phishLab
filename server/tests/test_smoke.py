"""脚手架冒烟测试：应用可导入、健康检查可用、OpenAPI 生成正常。"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_unauthenticated_blocked():
    r = client.get("/api/v1/campaigns")
    assert r.status_code == 401
    assert r.json()["code"] == 40101


def test_not_implemented_contract():
    """未实现端点返回统一 NOT_IMPLEMENTED 错误码而非 500。"""
    from app.core.security import create_token

    token = create_token(1, "scaffold")
    r = client.get(
        "/api/v1/campaigns/1/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 10002
