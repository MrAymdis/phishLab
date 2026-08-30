"""License 授权强制（fail-closed）测试：离线 RSA 验签 + 机器码部署绑定 + 演示模式兜底。

- .lic 验签走真实 _verify_offline 链路（monkeypatch LICENSE_PUBLIC_KEY）；
- 机器码绑定：签发时必须含 machine_code 且与本机指纹一致，整库拷贝/跨机部署即失效；
- 未激活 = 演示模式（试用功能 + 小配额），不再全量放行；
- 过期/吊销/机器不匹配 → gated 功能全关 + 新建资源被拒（LICENSE_INVALID）；
- 宏/EXE 载荷门控（红线 6）统一走 feature_enabled("payload") 单一事实源。
"""
import base64
import json
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import settings
from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.license.fingerprint import get_machine_code
from app.modules.license.models import LicenseInfo
from app.modules.license.service import (activate_offline, check_quota,
                                         feature_enabled, get_status)
from app.modules.template.models import AttachmentDownloadLog, AttachmentPayload
from app.modules.template.service import download_attachment, payload_enabled, upload_attachment

_BASE = 9300


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _gen_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def _sign(priv: bytes, payload: dict) -> str:
    key = serialization.load_pem_private_key(priv, password=None)
    sig = key.sign(_canonical(payload).encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def _lic_bytes(priv: bytes, **overrides) -> bytes:
    payload = {"license_no": f"PL-2026-{_BASE}", "customer": "测试客户",
               "edition": "flagship", "months": 12, "issued_at": "2026-08-25",
               "machine_code": get_machine_code()}
    payload.update({k: v for k, v in overrides.items() if v is not None})
    if "machine_code" in overrides and overrides["machine_code"] is None:
        payload.pop("machine_code", None)  # 模拟旧版无绑定 .lic
    data = dict(payload)
    data["signature"] = _sign(priv, payload)
    return json.dumps(data, ensure_ascii=False).encode()


@pytest.fixture()
def rsa_keys(monkeypatch):
    priv, pub = _gen_keys()
    monkeypatch.setattr(settings, "license_public_key", pub.decode())
    return priv, pub


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        db.query(LicenseInfo).delete()  # 恢复无 license 状态（demo 模式用例依赖）
        db.query(AttachmentPayload).filter(AttachmentPayload.id >= _BASE).delete()
        db.query(AttachmentDownloadLog).filter(AttachmentDownloadLog.payload_id >= _BASE).delete()
        db.commit()
    finally:
        db.close()


# ---------- 离线 License RSA 验签 + 机器码绑定 ----------


def test_offline_activate_ok(rsa_keys):
    priv, _ = rsa_keys
    db = SessionLocal()
    lic = _lic_bytes(priv)
    try:
        status = activate_offline(db, lic)
        assert status["edition"] == "flagship"
        assert status["customer_name"] == "测试客户"
        assert status["status"] == "active" and status["demo_mode"] is False
        assert status["remaining_days"] >= 355  # 12 个月
        row = db.query(LicenseInfo).first()
        assert row.activate_mode == "offline" and row.signature is not None
        assert row.machine_code == get_machine_code(), "激活应落库机器码绑定"
    finally:
        db.close()


def test_offline_replay_rejected(rsa_keys):
    db = SessionLocal()
    lic = _lic_bytes(rsa_keys[0])
    try:
        activate_offline(db, lic)
        with pytest.raises(BizError) as exc:
            activate_offline(db, lic)
        assert "防重放" in exc.value.message
    finally:
        db.close()


def test_offline_tampered_rejected(rsa_keys):
    db = SessionLocal()
    lic = json.loads(_lic_bytes(rsa_keys[0]))
    lic["edition"] = "trial"  # 篡改版本
    with pytest.raises(BizError) as exc:
        activate_offline(db, json.dumps(lic).encode())
    assert "签名校验失败" in exc.value.message
    assert get_status(db)["edition"] == "trial"  # 未落库（demo 模式）
    db.close()


def test_offline_bad_signature_rejected(rsa_keys):
    db = SessionLocal()
    lic = json.loads(_lic_bytes(rsa_keys[0]))
    lic["signature"] = base64.b64encode(b"forged").decode()
    with pytest.raises(BizError) as exc:
        activate_offline(db, json.dumps(lic).encode())
    assert "签名校验失败" in exc.value.message
    db.close()


def test_offline_no_public_key_rejected(monkeypatch):
    monkeypatch.setattr(settings, "license_public_key", "")
    db = SessionLocal()
    # 需要先有签名：无公钥时用假签名（机器码合法，走到公钥缺失拦截）
    lic = json.dumps({"license_no": "X-1", "customer": "c", "edition": "trial",
                      "months": 1, "issued_at": "2026-01-01",
                      "machine_code": get_machine_code(),
                      "signature": base64.b64encode(b"x").decode()}).encode()
    with pytest.raises(BizError) as exc:
        activate_offline(db, lic)
    assert "公钥" in exc.value.message  # fail-closed：未配置公钥拒绝激活
    db.close()


def test_offline_invalid_json_rejected(rsa_keys):
    db = SessionLocal()
    with pytest.raises(BizError):
        activate_offline(db, b"not json at all")
    with pytest.raises(BizError):
        activate_offline(db, b"[1,2,3]")
    db.close()


def test_offline_bad_months_rejected(rsa_keys):
    db = SessionLocal()
    lic = _lic_bytes(rsa_keys[0], months=99)
    with pytest.raises(BizError):
        activate_offline(db, lic)
    db.close()


def test_offline_wrong_machine_rejected(rsa_keys):
    """签发时绑定的是别的机器 → 激活拒绝（部署绑定）。"""
    db = SessionLocal()
    lic = _lic_bytes(rsa_keys[0], machine_code="deadbeef" * 8)
    with pytest.raises(BizError) as exc:
        activate_offline(db, lic)
    assert "不匹配" in exc.value.message
    assert get_status(db)["status"] == "demo"  # 未落库
    db.close()


def test_offline_missing_machine_rejected(rsa_keys):
    """旧版无 machine_code 字段的 .lic 一律拒绝（fail-closed）。"""
    db = SessionLocal()
    lic = _lic_bytes(rsa_keys[0], machine_code=None)
    with pytest.raises(BizError) as exc:
        activate_offline(db, lic)
    assert "machine_code" in exc.value.message
    db.close()


# ---------- fail-closed 强制：演示模式 / 过期 / 机器不匹配 ----------


def test_feature_enabled_demo_fail_closed():
    """未激活（无 license 行）→ 试用版能力兜底：AI 开，开放平台/载荷关（不再全量放行）。"""
    db = SessionLocal()
    assert feature_enabled(db, "ai") is True
    assert feature_enabled(db, "openapi") is False
    assert feature_enabled(db, "payload") is False
    db.close()


def test_openapi_gateway_blocked_in_demo():
    """未激活（演示模式）→ 开放平台网关路由级 fail-closed：直调 API 也被拒，不止隐藏菜单。"""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post("/openapi/v1/oauth/token",
                             json={"grant_type": "client_credentials",
                                   "app_id": "x", "app_secret": "y"})
    body = r.json()
    assert body["code"] != 0, "演示模式下开放平台网关应被 license 门控拒绝"
    assert "授权" in body["message"]
    db = SessionLocal()
    db.close()


def test_status_demo_mode():
    """未激活状态概览：demo 状态 + 演示小配额 + 本机机器码。"""
    db = SessionLocal()
    st = get_status(db)
    assert st["status"] == "demo" and st["demo_mode"] is True
    assert st["edition"] == "trial"
    assert st["features"]["openapi"] is False
    assert st["quotas"]["campaign"]["total"] == 20
    assert st["machine_code"] == get_machine_code()
    db.close()


def test_check_quota_demo_caps(monkeypatch):
    """未激活 → 演示小配额兜底，超限拒绝（不再无 license 放行）。"""
    from app.modules.license import service as lic_service

    monkeypatch.setattr(lic_service, "_usage",
                        lambda db: {"user": 0, "mail": 0, "sms": 0, "campaign": 21})
    db = SessionLocal()
    with pytest.raises(BizError) as exc:
        check_quota(db, "campaign", 1)
    assert "配额已用尽" in exc.value.message
    db.close()


def test_expired_license_fail_closed():
    """授权已过期 → gated 功能全关 + 新建资源被拒（禁止新建/投递）。"""
    db = SessionLocal()
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
                       machine_code=get_machine_code(),
                       expire_at=datetime.now() - timedelta(days=1)))
    db.commit()
    assert feature_enabled(db, "ai") is False
    assert payload_enabled(db) is False
    with pytest.raises(BizError) as exc:
        check_quota(db, "campaign", 1)
    assert "过期" in exc.value.message
    db.close()


def test_machine_mismatch_blocks_runtime():
    """数据库整库拷贝到别的机器 → 机器码不匹配：功能全关、新建被拒。"""
    db = SessionLocal()
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
                       machine_code="deadbeef" * 8,
                       expire_at=datetime.now() + timedelta(days=30)))
    db.commit()
    assert feature_enabled(db, "openapi") is False
    assert payload_enabled(db) is False
    with pytest.raises(BizError) as exc:
        check_quota(db, "campaign", 1)
    assert "不匹配" in exc.value.message
    db.close()


# ---------- 附件宏/EXE 载荷门控（红线 6） ----------


def test_payload_disabled_by_default(tmp_path, monkeypatch):
    """无 license 行（演示模式）→ 宏/EXE 一律拒绝，且不享受无 license 放行。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    assert payload_enabled(db) is False
    with pytest.raises(BizError):
        upload_attachment(db, account, "evil.exe", b"MZ\x90\x00")
    with pytest.raises(BizError):
        upload_attachment(db, account, "macro.docm", b"PK")
    db.close()


def test_payload_enabled_with_flagship(tmp_path, monkeypatch):
    """旗舰授权（active 未过期且本机绑定）→ 宏/EXE 按扩展名归类上传，下载留痕；良性文档不受影响。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
                       machine_code=get_machine_code(),
                       expire_at=datetime.now() + timedelta(days=30)))
    db.commit()
    try:
        assert payload_enabled(db) is True
        pid_exe = upload_attachment(db, account, "evil.exe", b"MZ\x90\x00", platform="Windows")
        pid_macro = upload_attachment(db, account, "macro.docm", b"PK", platform="Windows")
        assert db.get(AttachmentPayload, pid_exe).file_type == "exe"
        assert db.get(AttachmentPayload, pid_macro).file_type == "macro_doc"

        path, name = download_attachment(db, account, pid_exe, ip="1.2.3.4")
        assert name == "evil.exe"
        log = db.query(AttachmentDownloadLog).filter(
            AttachmentDownloadLog.payload_id == pid_exe).first()
        assert log is not None and log.action == "download"

        pid_doc = upload_attachment(db, account, "发票.docx", b"PK", platform="")
        assert db.get(AttachmentPayload, pid_doc).file_type == "benign_doc"
    finally:
        db.close()


def test_payload_download_blocked_without_license(tmp_path, monkeypatch):
    """授权失效（无 license）后宏附件禁止下载——下载即分发，再次过门。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
                       machine_code=get_machine_code(),
                       expire_at=datetime.now() + timedelta(days=30)))
    db.commit()
    pid = upload_attachment(db, account, "evil.exe", b"MZ\x90\x00")
    db.query(LicenseInfo).delete()  # 授权移除（如到期/吊销）
    db.commit()
    with pytest.raises(BizError) as exc:
        download_attachment(db, account, pid, ip="1.2.3.4")
    assert "未授权" in exc.value.message
    db.close()


def test_payload_expired_license_blocked(tmp_path, monkeypatch):
    """授权已过期 → 上传拒绝（过期即失效，不信任已上传但未过期的旧状态）。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
                       machine_code=get_machine_code(),
                       expire_at=datetime.now() - timedelta(days=1)))
    db.commit()
    assert payload_enabled(db) is False
    with pytest.raises(BizError):
        upload_attachment(db, account, "evil.exe", b"MZ\x90\x00")
    db.close()
