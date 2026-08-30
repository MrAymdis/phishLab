"""举报插件打包后端（任务 #3）：配置导出接口、域名白名单 fail-closed、message_id 重复上报拦截。

HTTP 全链路走 TestClient（真实路由 + 异常 handler）：
- 导出接口无 Key → 404/10404；有 Key → 明文 apiKey 附件 JSON + 审计
- 域名白名单配置后强制校验（非白名单域名 10001），未配置放行
- 同 message_id 二次上报 → 41002；X-Api-Key 无效 → 401/40101
"""
import datetime

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.modules.rbac.models import AuditLog
from app.modules.report.models import MailReport
from app.modules.settings.models import PlatformSetting

client = TestClient(app)


def _auth() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"Authorization": "Bearer " + jwt.encode(
        {"sub": "1", "username": "tester", "iat": now,
         "exp": now + datetime.timedelta(minutes=60)},
        settings.secret_key, algorithm="HS256",
    )}


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        db.execute(delete(MailReport))
        db.execute(delete(AuditLog).where(AuditLog.module == "report"))
        db.execute(delete(PlatformSetting).where(PlatformSetting.setting_key.like("report_%")))
        db.commit()
    finally:
        db.close()


def _regen_key() -> str:
    """重生成插件 Key 并返回明文（走导出接口，同时覆盖审计路径）。"""
    r = client.post("/api/v1/mail-reports/plugin-config/regen-key", headers=_auth())
    assert r.status_code == 200 and r.json()["code"] == 0
    r = client.get("/api/v1/mail-reports/plugin-config/export", headers=_auth())
    assert r.status_code == 200
    return r.json()["apiKey"]


# ---------- 配置导出 ----------

def test_export_config_without_key_404():
    r = client.get("/api/v1/mail-reports/plugin-config/export", headers=_auth())
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == 10404 and "尚未生成" in body["message"]


def test_export_config_downloads_plaintext_key_with_audit():
    r = client.post("/api/v1/mail-reports/plugin-config/regen-key", headers=_auth())
    assert r.status_code == 200
    r = client.get("/api/v1/mail-reports/plugin-config/export", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    # 配置文件直出（非 {code,message,data} 包裹）
    assert body["apiKey"].startswith("plr_") and body["apiKey"] != body.get("code")
    assert body["serverUrl"] == "http://testserver"  # base_url 去尾斜杠（客户端自拼路径）
    assert body["allowedDomains"] == [] and body["version"] == "1.0"
    assert "phishlab-plugin-config.json" in r.headers["content-disposition"]
    # 敏感出库审计（红线 2 取证口径）
    db = SessionLocal()
    row = db.query(AuditLog).filter(AuditLog.action == "export_plugin_config").first()
    db.close()
    assert row is not None and row.module == "report"


# ---------- 上报鉴权 ----------

def test_ingest_rejects_bad_api_key():
    r = client.post("/report/v1/mail", json={"from_addr": "a@b.com"},
                    headers={"X-Api-Key": "wrong"})
    assert r.status_code == 401 and r.json()["code"] == 40101


# ---------- 域名白名单 fail-closed ----------

def test_ingest_domain_whitelist_fail_closed():
    api_key = _regen_key()
    # 配置白名单只允许 corp.com
    r = client.put("/api/v1/mail-reports/plugin-config", headers=_auth(),
                   json={"allowedDomains": ["corp.com"], "webhookUrl": "", "autoclass": True})
    assert r.status_code == 200
    hdrs = {"X-Api-Key": api_key}
    # 白名单外域名 → 拒绝
    r = client.post("/report/v1/mail", headers=hdrs, json={
        "from_addr": "evil@x.com", "reporter_email": "victim@evil.com", "subject": "s"})
    assert r.status_code == 200 and r.json()["code"] == 10001
    assert "未在插件允许列表" in r.json()["message"]
    # 无 reporter_email → 同样拒绝
    r = client.post("/report/v1/mail", headers=hdrs, json={"from_addr": "evil@x.com"})
    assert r.json()["code"] == 10001
    # 白名单内域名（大小写不敏感）→ 放行
    r = client.post("/report/v1/mail", headers=hdrs, json={
        "from_addr": "evil@x.com", "reporter_email": "Staff@Corp.COM", "subject": "s"})
    assert r.status_code == 200 and r.json()["code"] == 0
    # 未配置白名单 → 任意域名放行
    client.put("/api/v1/mail-reports/plugin-config", headers=_auth(), json={
        "allowedDomains": [], "webhookUrl": "", "autoclass": True})
    r = client.post("/report/v1/mail", headers=hdrs, json={
        "from_addr": "evil@x.com", "reporter_email": "anyone@else.com", "subject": "s"})
    assert r.status_code == 200 and r.json()["code"] == 0


# ---------- 重复上报拦截 ----------

def test_ingest_duplicate_message_id_conflict():
    api_key = _regen_key()
    hdrs = {"X-Api-Key": api_key}
    payload = {"from_addr": "evil@x.com", "reporter_email": "a@b.com",
               "subject": "工资条", "message_id": "<abc123@mail>"}
    r = client.post("/report/v1/mail", headers=hdrs, json=payload)
    assert r.status_code == 200 and r.json()["code"] == 0
    r = client.post("/report/v1/mail", headers=hdrs, json=payload)
    assert r.status_code == 200 and r.json()["code"] == 41002
    assert "已举报过" in r.json()["message"]
    db = SessionLocal()
    assert db.query(MailReport).count() == 1
    db.close()
    # 无 message_id 可重复上报（不做拦截）
    r = client.post("/report/v1/mail", headers=hdrs, json={
        "from_addr": "evil@x.com", "reporter_email": "a@b.com", "subject": "工资条"})
    assert r.json()["code"] == 0


# ---------- 插件资产托管 ----------

def test_outlook_manifest_renders_base_url():
    r = client.get("/report/v1/plugin/outlook/manifest.xml?base=http://phish.example.com:5173")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    xml = r.text
    assert "http://phish.example.com:5173/report/v1/plugin/outlook/taskpane.html" in xml
    assert "http://phish.example.com:5173/report/v1/plugin/outlook/icon-80.png" in xml
    assert "{BASE}" not in xml  # 占位符全部注入
    assert "MessageReadCommandSurface" in xml
    # 非法 base（非 http/https，防 javascript: 注入）→ 拒绝
    r = client.get("/report/v1/plugin/outlook/manifest.xml?base=javascript:alert(1)")
    assert r.status_code == 200 and r.json()["code"] == 10001


def test_plugin_static_serves_icons_and_blocks_traversal():
    r = client.get("/report/v1/plugin/outlook/icon-16.png")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    # 路径穿越防护：目录外文件一律 404
    assert client.get("/report/v1/plugin/../../app/core/config.py").status_code == 404
    assert client.get("/report/v1/plugin/outlook/../secret.txt").status_code == 404


def test_webmail_zip_packs_assets():
    import io
    import zipfile

    r = client.get("/report/v1/plugin/webmail.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "phishlab-webmail-plugin.zip" in r.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert {"manifest.json", "background.js", "content.js", "popup.html",
            "icons/icon-32.png"} <= names
    # 配置 JSON（含 API Key）绝不进安装包——由导出接口单独交付
    assert not any("config" in n or "api" in n for n in names)


def test_export_config_base_param_override():
    """反代改写 Host 时，前端传浏览器可见 origin 覆盖 serverUrl。"""
    _regen_key()
    r = client.get("/api/v1/mail-reports/plugin-config/export?base=https://phish.example.com/",
                   headers=_auth())
    assert r.json()["serverUrl"] == "https://phish.example.com"
    r = client.get("/api/v1/mail-reports/plugin-config/export?base=ftp://bad", headers=_auth())
    assert r.json()["code"] == 10001
