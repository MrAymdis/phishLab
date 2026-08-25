"""离线 License RSA 验签 + 附件宏/EXE 载荷门控（红线 6）测试。

RSA 密钥在测试内动态生成（签发端逻辑与 scripts/gen_license.py 同构）；
平台验签走真实 _verify_offline 链路（monkeypatch LICENSE_PUBLIC_KEY）。
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
from app.modules.license.models import LicenseInfo
from app.modules.license.service import activate_offline, get_status
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
               "edition": "flagship", "months": 12, "issued_at": "2026-08-25"}
    payload.update(overrides)
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
        db.query(LicenseInfo).delete()  # 恢复无 license 状态（test_smoke 依赖）
        db.query(AttachmentPayload).filter(AttachmentPayload.id >= _BASE).delete()
        db.query(AttachmentDownloadLog).filter(AttachmentDownloadLog.payload_id >= _BASE).delete()
        db.commit()
    finally:
        db.close()


# ---------- 离线 License RSA 验签 ----------


def test_offline_activate_ok(rsa_keys):
    priv, _ = rsa_keys
    db = SessionLocal()
    lic = _lic_bytes(priv)
    try:
        status = activate_offline(db, lic)
        assert status["edition"] == "flagship"
        assert status["customer_name"] == "测试客户"
        assert status["remaining_days"] >= 355  # 12 个月
        row = db.query(LicenseInfo).first()
        assert row.activate_mode == "offline" and row.signature is not None
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
    assert get_status(db)["edition"] == "trial"  # 未落库
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
    # 需要先有签名：无公钥时用假签名（走不到验签，先被公钥缺失拦截）
    lic = json.dumps({"license_no": "X-1", "customer": "c", "edition": "trial",
                      "months": 1, "issued_at": "2026-01-01",
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


# ---------- 附件宏/EXE 载荷门控（红线 6） ----------


def test_payload_disabled_by_default(tmp_path, monkeypatch):
    """无 license 行（含无授权）→ 宏/EXE 一律拒绝，且不享受无 license 放行。"""
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
    """旗舰授权（active 未过期）→ 宏/EXE 按扩展名归类上传，下载留痕；良性文档不受影响。"""
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    db.add(LicenseInfo(license_key="PL-FLAG-X", edition="flagship", status="active",
                       user_quota=1, mail_quota=1, sms_quota=1, campaign_quota=1,
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
                       expire_at=datetime.now() - timedelta(days=1)))
    db.commit()
    assert payload_enabled(db) is False
    with pytest.raises(BizError):
        upload_attachment(db, account, "evil.exe", b"MZ\x90\x00")
    db.close()
