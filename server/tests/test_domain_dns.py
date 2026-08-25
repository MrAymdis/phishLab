"""演练域名 DNS 巡检测试：DMARC 状态按 p= 值存储与展示（reject/quarantine/none/fail/unknown），
不再用"有无记录"混淆 p=none 与 p=reject。DNS 全部 monkeypatch，不触真实网络。"""
import dns.exception
import dns.resolver
import pytest
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.channel.models import PhishDomain
from app.modules.channel.service import check_dns, list_domains


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    db = SessionLocal()
    db.execute(delete(PhishDomain))
    db.commit()
    db.close()


class _Txt:
    def __init__(self, text: str):
        self.strings = [text.encode()]


def _fake_resolve(records: dict, timeout_names: set = frozenset()):
    def fake(name, rdtype, lifetime=None):
        if name in timeout_names:
            raise dns.exception.Timeout()
        if name not in records:
            raise dns.resolver.NXDOMAIN()
        return [_Txt(records[name])]

    return fake


def _records(dmarc: str | None = None, domain: str = "drill-test.com") -> dict:
    """SPF/DKIM/MX 记录齐全，DMARC 记录可控。"""
    rec = {
        domain: "v=spf1 mx ~all",  # 同时覆盖 SPF TXT 与 MX 检查
        f"phish._domainkey.{domain}": "v=DKIM1; k=rsa; p=pubkey",
    }
    if dmarc is not None:
        rec[f"_dmarc.{domain}"] = dmarc
    return rec


def _seed_domain(db, domain: str = "drill-test.com") -> PhishDomain:
    d = PhishDomain(domain=domain, purpose="测试", dkim_selector="phish")
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _run_check(monkeypatch, dmarc=None, timeout_names=frozenset()):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(_records(dmarc), timeout_names))
    d = _seed_domain(db)
    result = check_dns(db, account, d.id)
    row = db.get(PhishDomain, d.id)
    db.close()
    return result, row


def test_dmarc_reject_stored_and_displayed(monkeypatch):
    result, row = _run_check(monkeypatch, dmarc="v=DMARC1; p=reject; rua=mailto:x@drill-test.com")
    assert row.dmarc_status == "reject"
    assert result["dmarc"] == "reject（拒收）"
    assert result["score"] == 100  # SPF/DKIM/DMARC/MX 各 25


def test_dmarc_quarantine(monkeypatch):
    result, row = _run_check(monkeypatch, dmarc="v=DMARC1; p=quarantine")
    assert row.dmarc_status == "quarantine"
    assert result["dmarc"] == "quarantine（垃圾箱）"
    assert result["score"] == 100


def test_dmarc_none(monkeypatch):
    result, row = _run_check(monkeypatch, dmarc="v=DMARC1; p=none")
    assert row.dmarc_status == "none"
    assert result["dmarc"] == "p=none（不拦截）"
    assert result["score"] == 100  # 有记录即计分，但展示区分 p=none 与 p=reject


def test_dmarc_no_record(monkeypatch):
    result, row = _run_check(monkeypatch, dmarc=None)
    assert row.dmarc_status == "fail"
    assert result["dmarc"] == "FAIL（无记录）"
    assert result["score"] == 75  # DMARC 无记录不计分


def test_dmarc_query_timeout(monkeypatch):
    result, row = _run_check(monkeypatch, timeout_names={"_dmarc.drill-test.com"})
    assert row.dmarc_status == "unknown"
    assert result["dmarc"] == "WARN（查询失败）"
    assert result["score"] == 75


def test_list_domains_uses_dmarc_policy_text(monkeypatch):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve(
            _records(dmarc="v=DMARC1; p=reject")))
        d = _seed_domain(db)
        check_dns(db, account, d.id)
        rows = list_domains(db, account)
        row = next(r for r in rows if r["domain"] == "drill-test.com")
        assert row["dmarc"] == "reject（拒收）"
    finally:
        db.close()
