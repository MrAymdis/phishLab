"""AI 对话 ChatBI 数据注入测试：意图检测 / 模板问法映射 / 表格化 / 集成查询。

红线 5 守卫由 ChatBI 管线本身承担（test_chatbi 已覆盖），此处验证对话层的
意图→查询→注入逻辑：命中数据意图时能拿到真实只读数据并表格化。
"""
import pytest

from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.ai import chatbi as chatbi_svc
from app.modules.ai.service import _fallback_queries, _rows_to_markdown, _wants_drill_data
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.org.models import EmpDept, EmpUser

_BASE = 9500


@pytest.fixture()
def seeded_db():
    db = SessionLocal()
    try:
        db.add(EmpDept(id=_BASE + 10, parent_id=0, path=f"/{_BASE + 10}", name="测试财务部"))
        db.add(EmpUser(id=_BASE + 1, name="注入张三", email=f"injectzhang{_BASE}@corp.com",
                       dept_id=_BASE + 10, status=1))
        db.add(Campaign(id=_BASE + 1, name="注入测试演练", type="email", status="completed",
                        creator_id=1, auth_confirmed=1, target_mode="manual", schedule_type="immediate"))
        from datetime import datetime

        db.add(CampaignTarget(id=_BASE + 100, campaign_id=_BASE + 1, user_id=_BASE + 1,
                              batch_no=1, token="injtk1", send_status="sent",
                              sent_at=datetime(2026, 8, 20, 10, 0, 0),
                              submit_flag=1, attach_run_count=0))
        db.commit()
        yield db
    finally:
        db.query(CampaignTarget).filter(CampaignTarget.id == _BASE + 100).delete()
        db.query(Campaign).filter(Campaign.id == _BASE + 1).delete()
        db.query(EmpUser).filter(EmpUser.id == _BASE + 1).delete()
        db.query(EmpDept).filter(EmpDept.id == _BASE + 10).delete()
        db.commit()
        db.close()


# ---------- 意图检测 ----------


def test_wants_drill_data_hits():
    for q in ("分析最近一次演练的效果", "各部门中招率", "帮我看看打开率", "风险画像"):
        assert _wants_drill_data(q) is True


def test_wants_drill_data_ignores_plain():
    for q in ("帮我写一个钓鱼邮件模板", "今天天气如何", "介绍一下平台"):
        assert _wants_drill_data(q) is False


# ---------- 模板问法映射 ----------


def test_fallback_queries_mapping():
    assert "各演练统计" in _fallback_queries("分析最近一次演练的效果")
    assert "各部门中招率" in _fallback_queries("各部门中招情况怎么样")
    assert "高危人员" in _fallback_queries("看看谁风险最高")
    assert _fallback_queries("介绍下平台") == []


# ---------- 表格化 ----------


def test_rows_to_markdown():
    md = _rows_to_markdown(["id", "name", "victim"], [[1, "演练A", 5], [2, "演练B", 3]])
    assert md.startswith("| id | name | victim |")
    assert "| 1 | 演练A | 5 |" in md
    # 超限截断
    rows = [[i, f"x{i}", i] for i in range(20)]
    md2 = _rows_to_markdown(["a", "b", "c"], rows)
    assert "仅展示前 12 行" in md2


# ---------- 集成：模板问法在 sqlite 全链路可查 ----------


@pytest.mark.asyncio
async def test_inject_query_returns_rows(seeded_db):
    """注入兜底问法"各演练统计"走完整管线：模板 SQL → 校验 → 权限注入 → 只读执行。"""
    account = seeded_db.get(SysAccount, 1)  # super_admin（全量）
    result = await chatbi_svc.ask_question(seeded_db, account, "各演练统计")
    assert result["rows"], "应返回注入测试演练的真实统计"
    cols = result["columns"]
    assert {"id", "name", "sent", "victim"} <= set(cols)
    row = next(r for r in result["rows"] if str(r[0]) == str(_BASE + 1))
    assert row[3] == 1  # victim=1（张三 submit_flag=1）
    md = _rows_to_markdown(cols, result["rows"])
    assert "注入测试演练" in md
