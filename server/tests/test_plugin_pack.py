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


# ---------- 网页邮箱合成降级信息 ----------

def test_ingest_degrade_annotates_remark():
    """网页邮箱 L2/L3 降级原因入举报备注，供研判知情；超长截断适配 remark 列容量。"""
    api_key = _regen_key()
    r = client.post("/report/v1/mail", headers={"X-Api-Key": api_key}, json={
        "from_addr": "a@b.com", "subject": "s", "degrade": "附件抓取失败：工资单.xlsx"})
    assert r.json()["code"] == 0
    rid = r.json()["data"]["id"]
    db = SessionLocal()
    row = db.query(MailReport).get(rid)
    db.close()
    assert row.handle_remark == "[插件降级] 附件抓取失败：工资单.xlsx"
    # 超长降级原因截断（handle_remark 列 512 字符）
    r = client.post("/report/v1/mail", headers={"X-Api-Key": api_key}, json={
        "from_addr": "a@b.com", "subject": "s", "message_id": "<degrade-long@x>",
        "degrade": "原因" * 300})
    assert r.json()["code"] == 0
    rid2 = r.json()["data"]["id"]
    db = SessionLocal()
    row2 = db.query(MailReport).get(rid2)
    db.close()
    assert len(row2.handle_remark) <= 512 and row2.handle_remark.startswith("[插件降级]")


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

def test_outlook_manifest_embeds_guide_and_requires_auth():
    """manifest 经鉴权端点导出：内置通道 Key（SourceLocation 查询参数），员工零配置；敏感出库审计。"""
    _regen_key()
    r = client.get("/api/v1/mail-reports/plugin-config/outlook-manifest?base=https://phish.example.com:5173",
                   headers=_auth())
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    # 下载文件名必须是 .xml：Outlook「添加自定义加载项」只认 .xml（曾经无此头 → 落 .bin 被拒）
    assert r.headers["content-disposition"].endswith('phishlab-outlook-manifest.xml"')
    xml = r.text
    assert "https://phish.example.com:5173/report/v1/plugin/outlook/taskpane.html?plrKey=plr_" in xml
    assert "https://phish.example.com:5173/report/v1/plugin/outlook/icon-80.png" in xml
    assert "{BASE}" not in xml and "{PLR_KEY}" not in xml  # 占位符全部注入
    assert "MessageReadCommandSurface" in xml
    assert "<TaskpaneId>" not in xml  # 1.1 架构下 Action 只允许 SourceLocation，出现即 Outlook 校验失败
    assert "<Version>1.2.0.0</Version>" in xml
    # Supertip Description 必须引用 LongString（曾放 ShortStrings → 校验报「LongStrings 中找不到资源 ID」）
    ss = xml.split("<bt:ShortStrings>")[1].split("</bt:ShortStrings>")[0]
    ls = xml.split("<bt:LongStrings>")[1].split("</bt:LongStrings>")[0]
    assert 'id="reportBtnTip"' in ls and 'id="reportBtnTip"' not in ss
    # 尾部斜杠去重（request.base_url 默认带 /，双斜杠会让资源 404）
    r = client.get("/api/v1/mail-reports/plugin-config/outlook-manifest?base=https://phish.example.com/",
                   headers=_auth())
    assert "https://phish.example.com/report/v1/" in r.text
    # Outlook 强制 manifest 内 URL 必须 https（http 连 localhost 都不豁免）→ http base 直接拒绝
    r = client.get("/api/v1/mail-reports/plugin-config/outlook-manifest?base=http://192.168.208.139:5173",
                   headers=_auth())
    assert r.json()["code"] == 10001 and "https" in r.json()["message"]
    # 非法 base（防 javascript: 注入）→ 拒绝
    r = client.get("/api/v1/mail-reports/plugin-config/outlook-manifest?base=javascript:alert(1)",
                   headers=_auth())
    assert r.json()["code"] == 10001
    # 敏感出库审计（红线 2 取证口径）
    db = SessionLocal()
    row = db.query(AuditLog).filter(AuditLog.action == "export_outlook_manifest").first()
    db.close()
    assert row is not None and row.module == "report"


def test_outlook_manifest_requires_key_and_auth():
    # 无 Key → 10404（内置 Key 的 manifest 必须先有 Key）
    r = client.get("/api/v1/mail-reports/plugin-config/outlook-manifest?base=https://phish.example.com",
                   headers=_auth())
    assert r.status_code == 404 and r.json()["code"] == 10404
    # 未登录 → 401
    assert client.get(
        "/api/v1/mail-reports/plugin-config/outlook-manifest?base=https://phish.example.com").status_code == 401
    # 旧公开 manifest 端点已移除（内置 Key 后必须鉴权）→ 404
    assert client.get("/report/v1/plugin/outlook/manifest.xml?base=https://phish.example.com").status_code == 404


def test_webmail_package_embeds_guide():
    """内置配置版扩展包：phishlab-guide.json 含明文 Key（审计），员工解压即用。"""
    import io
    import json
    import zipfile

    _regen_key()
    r = client.get("/api/v1/mail-reports/plugin-config/webmail-package?base=https://phish.example.com",
                   headers=_auth())
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "phishlab-webmail-plugin.zip" in r.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "phishlab-guide.json" in names and "manifest.json" in names
    guide = json.loads(zf.read("phishlab-guide.json"))
    assert guide["apiKey"].startswith("plr_") and guide["serverUrl"] == "https://phish.example.com"
    # 敏感出库审计
    db = SessionLocal()
    row = db.query(AuditLog).filter(AuditLog.action == "export_webmail_package").first()
    db.close()
    assert row is not None and row.module == "report"


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
    # 公开包绝不含任何引导配置（含 API Key）——内置配置版走鉴权端点 webmail-package
    assert not any("config" in n or "api" in n or "guide" in n for n in names)


def test_export_config_base_param_override():
    """反代改写 Host 时，前端传浏览器可见 origin 覆盖 serverUrl。"""
    _regen_key()
    r = client.get("/api/v1/mail-reports/plugin-config/export?base=https://phish.example.com/",
                   headers=_auth())
    assert r.json()["serverUrl"] == "https://phish.example.com"
    r = client.get("/api/v1/mail-reports/plugin-config/export?base=ftp://bad", headers=_auth())
    assert r.json()["code"] == 10001


# ---------- EML 归档（任务 #12） ----------

import base64 as b64_mod

from app.modules.report import service as report_service


def _make_eml() -> bytes:
    """多部分测试邮件：text/plain 正文 + 1 个附件。"""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Phisher <phish@evil.com>"
    msg["To"] = "victim@corp.com"
    msg["Subject"] = "紧急：账号验证"
    msg["Date"] = "Tue, 25 Aug 2026 10:00:00 +0800"
    msg["Message-ID"] = "<eml-test-1@evil.com>"
    msg.set_content("请立即点击链接验证您的账号。")
    msg.add_attachment(b"binary payload content", maintype="application",
                       subtype="octet-stream", filename="payload.bin")
    return msg.as_bytes()


def _ingest(eml: bytes | None = None, **extra) -> dict:
    """上报一封邮件（带 EML），返回响应体。"""
    api_key = _regen_key()
    payload = {"from_addr": "phish@evil.com", "reporter_email": "victim@corp.com",
               "subject": "紧急：账号验证", "message_id": "<eml-test-1@evil.com>", **extra}
    if eml is not None:
        payload["eml_base64"] = b64_mod.b64encode(eml).decode()
    r = client.post("/report/v1/mail", headers={"X-Api-Key": api_key}, json=payload)
    assert r.status_code == 200 and r.json()["code"] == 0
    return r.json()


def _list_report(rid: int) -> dict:
    r = client.get("/api/v1/mail-reports", headers=_auth())
    assert r.status_code == 200 and r.json()["code"] == 0
    return next(x for x in r.json()["data"]["list"] if x["id"] == rid)


def test_ingest_eml_archives_preview_download(tmp_path, monkeypatch):
    """Outlook 上报 EML：落盘 + 邮件头回填 + 预览解析 + 原件下载。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))  # 测试绝不写生产 static 目录
    eml = _make_eml()
    rid = _ingest(eml)["data"]["id"]

    # 落盘路径正确
    assert (tmp_path / "report_eml" / f"{rid}.eml").read_bytes() == eml

    # 列表 hasEml + 邮件头由 EML 回填（payload 未带 headers）
    row = _list_report(rid)
    assert row["hasEml"] is True
    assert "From:" in (row.get("headers") or "") and "phish@evil.com" in row["headers"]

    # 预览：元信息/正文/附件
    r = client.get(f"/api/v1/mail-reports/{rid}/preview", headers=_auth())
    assert r.status_code == 200 and r.json()["code"] == 0
    p = r.json()["data"]
    assert p["hasEml"] is True and p["emlSize"] == len(eml)
    assert "phish@evil.com" in p["from"] and "victim@corp.com" in p["to"]
    assert p["subject"] == "紧急：账号验证" and p["date"].startswith("Tue")
    assert "账号" in p["body"]
    assert p["attachments"] == [{"name": "payload.bin", "size": 22}]

    # EML 原件下载（字节一致）
    r = client.get(f"/api/v1/mail-reports/{rid}/eml", headers=_auth())
    assert r.status_code == 200 and r.headers["content-type"].startswith("message/rfc822")
    assert f"report-{rid}.eml" in r.headers["content-disposition"]
    assert r.content == eml


def test_ingest_eml_oversize_skips_archive(tmp_path, monkeypatch):
    """EML 超限静默跳过归档，上报本身不受影响。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    monkeypatch.setattr(report_service, "_EML_MAX_BYTES", 64)
    rid = _ingest(_make_eml())["data"]["id"]
    row = _list_report(rid)
    assert row["hasEml"] is False
    assert not (tmp_path / "report_eml").exists()
    r = client.get(f"/api/v1/mail-reports/{rid}/preview", headers=_auth())
    assert r.json()["data"]["hasEml"] is False
    assert client.get(f"/api/v1/mail-reports/{rid}/eml", headers=_auth()).status_code == 404


def test_ingest_eml_invalid_base64_and_garbage(tmp_path, monkeypatch):
    """非法 base64 / 不像邮件的内容：不入库归档，上报照常成功。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    # 非法 base64
    rid1 = _ingest(None, eml_base64="@@@not-base64@@@", message_id="<garbage-1@x>")["data"]["id"]
    # 合法 base64 但无邮件头块（随机垃圾）
    rid2 = _ingest(None, eml_base64=b64_mod.b64encode(b"hello world").decode(),
                   message_id="<garbage-2@x>")["data"]["id"]
    assert _list_report(rid1)["hasEml"] is False
    assert _list_report(rid2)["hasEml"] is False
    assert not (tmp_path / "report_eml").exists()


def test_preview_eml_404_when_report_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    assert client.get("/api/v1/mail-reports/999999/preview", headers=_auth()).status_code == 404
    assert client.get("/api/v1/mail-reports/999999/eml", headers=_auth()).status_code == 404
