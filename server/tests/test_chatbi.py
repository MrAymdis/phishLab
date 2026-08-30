"""ChatBI 安全管线测试：校验拒绝非法 SQL / 表白名单 / 权限注入 / 只读执行 / 审计。

红线 5 约束的落地验证：任何绕过校验的输入必须被拒绝（fail-closed），
部门/本人数据权限必须注入到最终执行的 SQL。
"""
import pytest
from sqlalchemy import delete, select

from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.ai import chatbi
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.org.models import EmpDept, EmpUser
from app.modules.rbac.models import AuditLog, SysAccountRole, SysRole
from app.modules.report.models import MailReport

# 种子 ID 段：全部用 9000+，测试结束清理，避免与既有测试/数据冲突
_BASE = 9000


@pytest.fixture()
def seeded_db():
    """种子：2 部门 3 员工 1 演练 3 目标 1 举报 + 3 种数据范围账号。"""
    db = SessionLocal()
    try:
        db.add(EmpDept(id=_BASE + 10, parent_id=0, path=f"/{_BASE + 10}", name="财务部"))
        db.add(EmpDept(id=_BASE + 11, parent_id=0, path=f"/{_BASE + 11}", name="技术部"))
        db.add(EmpUser(id=_BASE + 1, name="张三", email=f"zhangsan{_BASE}@corp.com", dept_id=_BASE + 10, status=1))
        db.add(EmpUser(id=_BASE + 2, name="李四", email=f"lisi{_BASE}@corp.com", dept_id=_BASE + 11, status=1))
        db.add(EmpUser(id=_BASE + 3, name="王五", email=f"wangwu{_BASE}@corp.com", dept_id=_BASE + 10, status=1))
        db.add(Campaign(id=_BASE + 1, name="ChatBI 测试演练", type="email", status="completed",
                        creator_id=1, auth_confirmed=1, target_mode="manual", schedule_type="immediate"))
        from datetime import datetime

        for uid, flag, attach in ((_BASE + 1, 1, 0), (_BASE + 2, 0, 0), (_BASE + 3, 0, 2)):
            db.add(CampaignTarget(
                id=uid + 100, campaign_id=_BASE + 1, user_id=uid, batch_no=1,
                token=f"tk{uid}", send_status="sent", sent_at=datetime(2026, 8, 20, 10, 0, 0),
                submit_flag=flag, attach_run_count=attach,
            ))
        db.add(MailReport(id=_BASE + 1, channel="email", reporter_user_id=_BASE + 1,
                          reporter_email=f"zhangsan{_BASE}@corp.com", subject="测试举报",
                          classification="drill"))
        # 角色与账号：全量 / 本部门 / 仅本人 / 无角色
        db.add(SysRole(id=_BASE + 1, code="dept_role", name="部门角色", data_scope=3))
        db.add(SysRole(id=_BASE + 2, code="self_role", name="本人角色", data_scope=4))
        db.add(SysAccount(id=_BASE + 1, username="chatbi_full", password_hash="x", real_name="全量", status=1))
        db.add(SysAccount(id=_BASE + 2, username="chatbi_dept", password_hash="x", real_name="部门", status=1,
                          emp_user_id=_BASE + 1))  # 张三（财务部）
        db.add(SysAccount(id=_BASE + 3, username="chatbi_self", password_hash="x", real_name="本人", status=1,
                          emp_user_id=_BASE + 1))
        db.add(SysAccount(id=_BASE + 4, username="chatbi_norole", password_hash="x", real_name="无角色", status=1))
        db.add(SysAccountRole(account_id=_BASE + 1, role_id=1))  # conftest 的 super_admin
        db.add(SysAccountRole(account_id=_BASE + 2, role_id=_BASE + 1))
        db.add(SysAccountRole(account_id=_BASE + 3, role_id=_BASE + 2))
        db.commit()
        yield db
    finally:
        # 清理本文件种子（按子表→父表顺序；SysAccountRole 为复合主键；
        # AuditLog 自增 id 不可按 id 段删，按账号段清）
        for model in (CampaignTarget, MailReport, Campaign, SysAccount,
                      SysRole, EmpUser, EmpDept):
            db.execute(delete(model).where(model.id >= _BASE))
        db.execute(delete(SysAccountRole).where(SysAccountRole.account_id >= _BASE))
        db.execute(delete(AuditLog).where(AuditLog.account_id >= _BASE))
        db.commit()
        db.close()


def _account(db, uid):
    return db.get(SysAccount, uid)


@pytest.mark.asyncio
async def test_validate_rejects_unsafe_sql():
    for bad in ("DROP TABLE campaign", "SELECT * FROM users",
                "SELECT * FROM campaign; DROP TABLE campaign",
                "INSERT INTO campaign VALUES (1)"):
        with pytest.raises(BizError):
            chatbi._validate_sql(bad)
    # LIMIT 强制：缺省补 100，超出封顶 200
    assert "LIMIT 100" in chatbi._validate_sql("SELECT id FROM campaign")
    assert "LIMIT 200" in chatbi._validate_sql("SELECT id FROM campaign LIMIT 99999")


@pytest.mark.asyncio
async def test_super_admin_full_data_no_injection(seeded_db):
    db = seeded_db
    acct = _account(db, _BASE + 1)
    result = await chatbi.ask_question(db, acct, "各部门中招对比")
    assert result["title"] == "部门中招对比"
    rows = {r[0]: r[2] for r in result["rows"]}  # dept -> victim
    assert rows == {"财务部": 2, "技术部": 0}  # 张三 submit + 王五 attach_run
    assert "dept_id IN" not in result["sql"] and "user_id IN" not in result["sql"]


@pytest.mark.asyncio
async def test_dept_scope_injected(seeded_db):
    db = seeded_db
    acct = _account(db, _BASE + 2)  # 财务部（scope 3）
    result = await chatbi.ask_question(db, acct, "各部门中招对比")
    # 注入后只返回本部门，SQL 中带部门条件
    rows = [r[0] for r in result["rows"]]
    assert rows == ["财务部"]
    assert "dept_id IN" in result["sql"] or "user_id IN (SELECT id FROM emp_user WHERE dept_id IN" in result["sql"]


@pytest.mark.asyncio
async def test_self_only_scope_injected(seeded_db):
    db = seeded_db
    acct = _account(db, _BASE + 3)  # 仅本人（张三）
    result = await chatbi.ask_question(db, acct, "中招次数最多的员工 TOP10")
    assert result["rows"] == [["张三", "财务部", 1]]  # 仅张三的 submit，无王五 attach_run
    assert f"user_id = {_BASE + 1}" in result["sql"]


@pytest.mark.asyncio
async def test_no_role_fail_closed(seeded_db):
    db = seeded_db
    with pytest.raises(BizError) as exc:
        await chatbi.ask_question(db, _account(db, _BASE + 4), "各部门中招对比")
    assert exc.value.code == 40302  # PERM_DENIED


@pytest.mark.asyncio
async def test_unsupported_question_rejected(seeded_db):
    db = seeded_db
    with pytest.raises(BizError):
        await chatbi.ask_question(db, _account(db, _BASE + 1), "今天天气如何")


@pytest.mark.asyncio
async def test_suggestion_phrasings_supported(seeded_db):
    """概览/报表页的建议问法与占位示例问法都能命中模板（不再落入兜底报错）。"""
    db = seeded_db
    acct = _account(db, _BASE + 1)
    cases = [
        ("本月各部门中招率对比", "部门中招对比"),      # 概览页占位示例
        ("财务部中招率", "部门中招对比"),              # 报表页占位示例（X部中招 问法）
        ("近7天举报趋势", "举报趋势（按天）"),          # 概览页建议
        ("高风险人员名单", "高危人员（风险等级 3）"),   # 概览页建议
        ("培训通过率最低的部门", "培训通过率最低的部门"),  # 概览页建议
    ]
    for question, title in cases:
        result = await chatbi.ask_question(db, acct, question)
        assert result["title"] == title, f"{question} → {result['title']}"


@pytest.mark.asyncio
async def test_template_first_skips_llm(seeded_db, monkeypatch):
    """命中模板的问题不经 LLM（推理模型单次调用 20-60s），未命中才走 LLM。"""
    db = seeded_db
    calls: list[str] = []

    async def fake_llm(d, a, q, since):
        calls.append(q)
        return None

    monkeypatch.setattr(chatbi, "_ask_via_llm", fake_llm)
    result = await chatbi.ask_question(db, _account(db, _BASE + 1), "各部门中招对比")
    assert result["title"] == "部门中招对比" and calls == []
    with pytest.raises(BizError):
        await chatbi.ask_question(db, _account(db, _BASE + 1), "哪些员工没有打开邮件")
    assert calls == ["哪些员工没有打开邮件"]


@pytest.mark.asyncio
async def test_audit_logged(seeded_db):
    db = seeded_db
    await chatbi.ask_question(db, _account(db, _BASE + 1), "近7天中招趋势")
    audit = db.scalar(
        select(AuditLog).where(AuditLog.account_id == _BASE + 1, AuditLog.action == "chatbi_ask")
        .order_by(AuditLog.id.desc())
    )
    assert audit is not None
    assert audit.detail["question"] == "近7天中招趋势"
    assert "SELECT" in audit.detail["sql"]
