"""伪装发件人 From 地址写入校验：公共邮箱通道（QQ/163 等）下发信时 From 会被强制改写为发送账号，
被冒充 From 域 DMARC 强制（p=reject/quarantine）时投递不生效——无效数据一律拒绝、不留存。
"""
import dns.exception
import dns.resolver
import pytest
from sqlalchemy import delete, func, select

from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.channel.models import SendChannel, SenderProfile
from app.modules.channel.service import create_sender_profile, update_sender_profile


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    db = SessionLocal()
    db.execute(delete(SenderProfile))
    db.execute(delete(SendChannel))
    db.commit()
    db.close()


def _seed_channel(db, *, name, username, is_default=0):
    ch = SendChannel(
        name=name, type="smtp", status="normal", is_default=is_default,
        smtp_host="smtp.qq.com", smtp_port=465, smtp_encrypt="ssl",
        smtp_username=username,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _payload(**over):
    base = {"name": "财务部", "channel_type": "mail", "display_name": "财务部"}
    base.update(over)
    return base


def test_public_channel_rejects_spoofed_from():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        ch = _seed_channel(db, name="QQ通道", username="xmkmsec@qq.com")
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="admin@qq.com"))
        assert "公共邮箱" in ei.value.message
        # 拒绝 = 不留存
        assert db.scalar(select(func.count()).select_from(SenderProfile)) == 0
    finally:
        db.close()


def test_public_channel_accepts_from_equals_account():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        ch = _seed_channel(db, name="QQ通道", username="xmkmsec@qq.com")
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="xmkmsec@qq.com"))
        row = db.get(SenderProfile, pid)
        assert row is not None and row.from_addr == "xmkmsec@qq.com"
    finally:
        db.close()


def test_public_channel_accepts_empty_from():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        ch = _seed_channel(db, name="QQ通道", username="xmkmsec@qq.com")
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr=None))
        assert db.get(SenderProfile, pid) is not None  # 留空 = 仅显示名伪装，放行
    finally:
        db.close()


def test_company_channel_accepts_spoofed_from():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        ch = _seed_channel(db, name="公司域", username="notify@drill-domain.com")
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="ceo@drill-domain.com"))
        row = db.get(SenderProfile, pid)
        assert row is not None and row.from_addr == "ceo@drill-domain.com"
    finally:
        db.close()


def test_update_rejects_invalid_from_after_channel_change():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        company = _seed_channel(db, name="公司域", username="notify@drill-domain.com")
        pid = create_sender_profile(db, account, _payload(channel_id=company.id, from_addr="ceo@drill-domain.com"))
        qq = _seed_channel(db, name="QQ通道", username="xmkmsec@qq.com")
        with pytest.raises(BizError) as ei:
            update_sender_profile(db, account, pid, _payload(channel_id=qq.id, from_addr="ceo@drill-domain.com"))
        assert "公共邮箱" in ei.value.message
        row = db.get(SenderProfile, pid)
        assert row.channel_id == company.id  # 拒绝后原值保持
    finally:
        db.close()


def test_no_channel_resolves_default_public_and_rejects():
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        _seed_channel(db, name="QQ默认", username="xmkmsec@qq.com", is_default=1)
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=None, from_addr="admin@qq.com"))
        assert "公共邮箱" in ei.value.message
    finally:
        db.close()


# ---------- DMARC 投递有效性层（DNS 全部 monkeypatch，不触真实网络） ----------

class _Txt:
    """伪造 dns TXT rdata：仅需 .strings 属性（bytes 片段列表）。"""

    def __init__(self, text: str):
        self.strings = [text.encode()]


def _fake_resolve(records: dict, timeout_names: set = frozenset()):
    """伪造 dns.resolver.resolve：records[name] -> TXT；timeout_names 内抛超时；其余 NXDOMAIN。"""

    def fake(name, rdtype, lifetime=None):
        if name in timeout_names:
            raise dns.exception.Timeout()
        if name not in records:
            raise dns.resolver.NXDOMAIN()
        return [_Txt(records[name])]

    return fake


def _company_channel(db):
    return _seed_channel(db, name="公司域", username="notify@drill-domain.com")


def test_company_channel_rejects_external_from_with_dmarc_reject(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            {"_dmarc.qq.com": "v=DMARC1; p=reject; rua=mailto:dmarc@qq.com"}))
        ch = _company_channel(db)
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="hr@qq.com"))
        assert "DMARC" in ei.value.message and "p=reject" in ei.value.message
        assert db.scalar(select(func.count()).select_from(SenderProfile)) == 0  # 拒绝 = 不留存
    finally:
        db.close()


def test_company_channel_rejects_external_from_with_dmarc_quarantine(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            {"_dmarc.spoofed.com": "v=DMARC1; p=quarantine"}))
        ch = _company_channel(db)
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="ceo@spoofed.com"))
        assert "DMARC" in ei.value.message
    finally:
        db.close()


def test_company_channel_accepts_external_from_without_dmarc(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve({}))  # 全 NXDOMAIN：无 DMARC 记录
        ch = _company_channel(db)
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="ceo@no-dmarc.com"))
        assert db.get(SenderProfile, pid).from_addr == "ceo@no-dmarc.com"
    finally:
        db.close()


def test_company_channel_accepts_external_from_with_p_none(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            {"_dmarc.monitor.com": "v=DMARC1; p=none; rua=mailto:dmarc@monitor.com"}))
        ch = _company_channel(db)
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="hr@monitor.com"))
        assert db.get(SenderProfile, pid).from_addr == "hr@monitor.com"
    finally:
        db.close()


def test_same_domain_alias_skips_dmarc_check(monkeypatch):
    """同域别名（notify@drill-domain.com → hr@drill-domain.com）经通道认证 DMARC 自然通过，不查 DNS。"""
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            {"_dmarc.drill-domain.com": "v=DMARC1; p=reject"}))
        ch = _company_channel(db)
        pid = create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="hr@drill-domain.com"))
        assert db.get(SenderProfile, pid).from_addr == "hr@drill-domain.com"
    finally:
        db.close()


def test_dns_timeout_rejects_save(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve({}, timeout_names={"_dmarc.unknown.com"}))
        ch = _company_channel(db)
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="hr@unknown.com"))
        assert "超时" in ei.value.message
    finally:
        db.close()


def test_org_domain_fallback_enforced(monkeypatch):
    """子域无 DMARC 记录时按 RFC 7489 §6.6.3 查组织域，组织域强制同样拒绝。"""
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            {"_dmarc.corp.com": "v=DMARC1; p=quarantine"}))
        ch = _company_channel(db)
        with pytest.raises(BizError) as ei:
            create_sender_profile(db, account, _payload(channel_id=ch.id, from_addr="hr@sub.corp.com"))
        assert "DMARC" in ei.value.message
    finally:
        db.close()
