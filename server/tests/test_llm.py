"""LLM Provider 适配层测试：SSE 解析 / Key 加密与掩码 / 降级 / ChatBI LLM 兜底 / 用量。

FakeClient 注入方式：monkeypatch `app.modules.ai.llm._CLIENT_CLASSES`——
get_client 校验（类型支持、data_outbound）走真实逻辑，仅网络层替换为假实现。
"""
import asyncio
import json

import httpx
import pytest

from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.ai import chatbi, llm
from app.modules.ai.models import AiDraft, AiMessage, AiProvider, AiSession, AiUsageStat
from app.modules.ai.service import (
    chat_stream, create_provider, delete_provider, list_providers, update_provider,
)
from app.modules.ai.service import test_provider as svc_test_provider  # noqa: N813（别名避免被 pytest 收集）
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.org.models import EmpDept, EmpUser
from app.modules.rbac.models import AuditLog

_BASE = 9100


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect(gen):
    return [json.loads(frame["data"]) async for frame in gen]  # SSE 帧解包


def _account(db):
    return db.get(SysAccount, 1)


class FakeClient:
    """假 LLM 客户端：chat 返回可控内容（默认合法 SQL），stream 两 token。"""

    type = "local"

    def __init__(self, provider, api_key):
        self.provider = provider
        self.api_key = api_key
        self.reply = "SELECT 1"

    async def chat(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048):
        return {"content": self.reply, "tokens_in": 11, "tokens_out": 22}

    async def stream(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048):
        for ch in ("你好", "，平台"):
            yield {"type": "token", "content": ch}
        yield {"type": "usage", "tokens_in": 11, "tokens_out": 22}


def _patch_llm(monkeypatch, reply: str):
    """把 local 类替换为固定回复的假客户端（chat 路径）。"""
    class FakeChatOnly:
        def __init__(self, p, k):  # noqa: N803
            pass

        async def chat(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048):
            return {"content": reply, "tokens_in": 1, "tokens_out": 1}

    monkeypatch.setattr(llm, "_CLIENT_CLASSES", {"local": FakeChatOnly})


@pytest.fixture()
def db():
    sess = SessionLocal()
    yield sess
    sess.close()


@pytest.fixture()
def provider(db):
    p = AiProvider(id=_BASE + 1, name="test-local", type="local",
                   endpoint="http://127.0.0.1:9/v1", model="mock-model", enabled=1)
    db.add(p)
    db.commit()
    return p


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (AiMessage, AiSession, AiUsageStat, AiDraft):
            db.query(m).delete()
        db.query(AiProvider).filter(AiProvider.id >= _BASE).delete()
        db.query(AuditLog).filter(AuditLog.module == "ai").delete()
        db.query(CampaignTarget).filter(CampaignTarget.campaign_id >= _BASE).delete()
        db.query(Campaign).filter(Campaign.id >= _BASE).delete()
        db.query(EmpUser).filter(EmpUser.id >= _BASE).delete()
        db.query(EmpDept).filter(EmpDept.id >= _BASE).delete()
        db.commit()
    finally:
        db.close()


# ---------- SSE 解析（真实客户端 + MockTransport） ----------


def test_openai_stream_parses_sse():
    sse = (
        'data: {"choices":[{"delta":{"content":"中"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"招"}}]}\n\n'
        'data: {"choices":[{"delta":{},"usage":{"prompt_tokens":5,"completion_tokens":9}}]}\n\n'
        "data: [DONE]\n\n"
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=sse))
    p = AiProvider(id=1, name="t", type="openai", endpoint="http://x/v1", model="m")
    client = llm.OpenAICompatClient(p, "sk-test")
    client.http = httpx.AsyncClient(transport=transport)

    async def run():
        tokens, usage = [], None
        async for frame in client.stream([{"role": "user", "content": "hi"}]):
            if frame["type"] == "token":
                tokens.append(frame["content"])
            elif frame["type"] == "usage":
                usage = frame
        return tokens, usage

    tokens, usage = _run(run())
    assert tokens == ["中", "招"]
    assert usage["tokens_in"] == 5 and usage["tokens_out"] == 9


def test_anthropic_stream_parses_sse():
    sse = (
        'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":7}}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"安"}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"全"}}\n\n'
        'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":13}}\n\n'
        'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=sse))
    p = AiProvider(id=1, name="t", type="claude", endpoint="http://x/v1", model="m")
    client = llm.AnthropicClient(p, "sk-ant-test")
    client.http = httpx.AsyncClient(transport=transport)

    async def run():
        tokens, usage = [], None
        async for frame in client.stream([{"role": "user", "content": "hi"}]):
            if frame["type"] == "token":
                tokens.append(frame["content"])
            elif frame["type"] == "usage":
                usage = frame
        return tokens, usage

    tokens, usage = _run(run())
    assert tokens == ["安", "全"]
    assert usage["tokens_in"] == 7 and usage["tokens_out"] == 13


# ---------- Provider CRUD：Key 加密 + 掩码 ----------


def test_provider_crud_key_encrypted(db):
    acct = _account(db)
    created = create_provider(db, acct, {
        "name": "openai 主", "type": "openai",
        "endpoint": "https://api.openai.com/v1", "api_key": "sk-secret1234567890",
        "model": "gpt-4o-mini", "enabled": True,
    })
    assert created["api_key_masked"].startswith("sk-s") and "****" in created["api_key_masked"]
    # 落库密文：非明文（红线 2）
    row = db.get(AiProvider, created["id"])
    assert row.api_key_enc is not None
    assert b"sk-secret1234567890" not in row.api_key_enc
    # 列表掩码一致
    item = next(i for i in list_providers(db) if i["id"] == created["id"])
    assert item["api_key_masked"] == "sk-s****7890"
    # 更新：api_key 留空不更换 Key
    update_provider(db, acct, created["id"], {"name": "openai 主", "type": "openai", "enabled": False})
    row2 = db.get(AiProvider, created["id"])
    assert row2.api_key_enc == row.api_key_enc and row2.enabled == 0
    # 删除
    delete_provider(db, acct, created["id"])
    assert db.get(AiProvider, created["id"]) is None


def test_provider_validation(db):
    acct = _account(db)
    with pytest.raises(BizError):
        create_provider(db, acct, {"name": "x", "type": "aliyun", "api_key": "k"})
    with pytest.raises(BizError):
        create_provider(db, acct, {"name": "x", "type": "openai"})  # 非 local 缺 key


def test_data_outbound_blocks_cloud(db):
    p = AiProvider(id=_BASE + 2, name="no-out", type="openai", enabled=1, data_outbound=0)
    db.add(p)
    db.commit()
    with pytest.raises(BizError) as exc:
        llm.get_client(db, p)
    assert "不外发" in exc.value.message


def test_wenxin_not_supported(db):
    p = AiProvider(id=_BASE + 3, name="wx", type="wenxin", enabled=1)
    db.add(p)
    db.commit()
    with pytest.raises(BizError) as exc:
        llm.get_client(db, p)
    assert "暂未接入" in exc.value.message


# ---------- Copilot 降级与 LLM 路径 ----------


def test_copilot_falls_back_local_without_provider(db):
    gen = chat_stream(db, _account(db), {"message": "分析演练效果"})
    frames = _run(_collect(gen))
    types = [f["type"] for f in frames]
    assert types[-1] == "done" and all(t == "token" for t in types[:-1])  # 本地回复无 usage 帧
    # 回复已存库
    msg = db.query(AiMessage).filter(AiMessage.role == "assistant").first()
    assert msg is not None and "中招" in msg.content


def test_copilot_llm_path_with_usage(db, provider, monkeypatch):
    monkeypatch.setattr(llm, "_CLIENT_CLASSES", {"local": FakeClient})
    gen = chat_stream(db, _account(db), {"message": "帮我分析"})
    frames = _run(_collect(gen))
    contents = "".join(f["content"] for f in frames if f["type"] == "token")
    assert contents == "你好，平台"
    assert any(f["type"] == "done" for f in frames)
    # 回复与用量落库
    msg = db.query(AiMessage).order_by(AiMessage.id.desc()).first()
    assert msg.role == "assistant" and msg.content == "你好，平台"
    assert msg.tokens_in == 11 and msg.tokens_out == 22
    usage = db.query(AiUsageStat).filter(AiUsageStat.provider_id == provider.id).first()
    assert usage is not None and usage.call_count == 1


# ---------- ChatBI：LLM 生成走同一安全管线，失败兜底规则引擎 ----------


def _seed_chatbi_data(db):
    from datetime import datetime

    db.add(EmpDept(id=_BASE + 20, parent_id=0, path=f"/{_BASE + 20}", name="测试部"))
    db.add(EmpUser(id=_BASE + 20, name="测试员工", email=f"t{_BASE}@corp.com",
                   dept_id=_BASE + 20, status=1))
    db.add(Campaign(id=_BASE + 20, name="LLM 测试演练", type="email", status="completed",
                    creator_id=1, auth_confirmed=1, target_mode="manual", schedule_type="immediate"))
    db.add(CampaignTarget(id=_BASE + 20, campaign_id=_BASE + 20, user_id=_BASE + 20, batch_no=1,
                          token=f"tk{_BASE}", send_status="sent",
                          sent_at=datetime(2026, 8, 1, 9, 0), submit_flag=1))
    db.commit()


@pytest.mark.asyncio
async def test_chatbi_llm_bad_sql_rejected(db, provider, monkeypatch):
    """长尾问法（未命中模板）走 LLM：LLM SQL 被校验层拒绝 → fail-closed 报错。"""
    _patch_llm(monkeypatch, "SELECT * FROM users LIMIT 10")
    with pytest.raises(BizError) as exc:
        await chatbi.ask_question(db, _account(db), "各部门的邮件打开率")
    assert "暂不支持该问法" in exc.value.message


@pytest.mark.asyncio
async def test_chatbi_llm_valid_sql(db, provider, monkeypatch):
    """长尾问法（未命中模板）走 LLM：合法 SQL 走同一校验/注入/只读管线。"""
    _seed_chatbi_data(db)
    sql = (
        "SELECT d.name AS dept, COUNT(t.id) AS sent "
        "FROM campaign_target t JOIN emp_user u ON u.id = t.user_id "
        "JOIN emp_dept d ON d.id = u.dept_id "
        "WHERE t.send_status IN ('sent') AND t.sent_at >= '2026-07-01 00:00:00' "
        "GROUP BY d.name ORDER BY sent DESC LIMIT 10"
    )
    _patch_llm(monkeypatch, sql)
    result = await chatbi.ask_question(db, _account(db), "各部门的邮件打开率")
    assert result["title"] == "AI 问数"
    assert "dept" in result["columns"] and result["total"] >= 1
    assert result["sql"].startswith("SELECT") and "LIMIT" in result["sql"]
    # 权限注入仍生效（super_admin 全量 → 无注入条件）
    assert "user_id IN" not in result["sql"] and "dept_id IN" not in result["sql"]


# ---------- 连通性测试 ----------


def test_provider_test_ping(db, provider, monkeypatch):
    monkeypatch.setattr(llm, "_CLIENT_CLASSES", {"local": FakeClient})
    result = _run(svc_test_provider(db, provider.id))
    assert result["ok"] is True and result["latency_ms"] >= 0
    assert result["tokens_in"] == 11
