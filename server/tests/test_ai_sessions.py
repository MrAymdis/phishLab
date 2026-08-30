"""AI 会话消息明细测试（HTTP 全链路）：正序返回 + 账号数据隔离（越权按 404 处理）。"""
import datetime

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.modules.account.models import SysAccount
from app.modules.ai.models import AiMessage, AiSession

_BASE = 9600

client = TestClient(app)


def _token(account_id: int) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"Authorization": "Bearer " + jwt.encode(
        {"sub": str(account_id), "username": f"t{account_id}", "iat": now,
         "exp": now + datetime.timedelta(minutes=60)},
        settings.secret_key, algorithm="HS256",
    )}


@pytest.fixture()
def seeded():
    from sqlalchemy import select as sa_select

    from app.modules.rbac.models import SysAccountRole, SysRole

    db = SessionLocal()
    db.add(SysAccount(id=_BASE + 101, username=f"aisess{_BASE}a", password_hash="x",
                      real_name="会话测试甲", status=1))
    db.add(SysAccount(id=_BASE + 102, username=f"aisess{_BASE}b", password_hash="x",
                      real_name="会话测试乙", status=1))
    # super_admin 角色直通（require_perm 硬编码放行），仅挂测试账号，测试后清理
    admin_role = db.scalar(sa_select(SysRole).where(SysRole.code == "super_admin"))
    assert admin_role is not None, "种子数据缺少 super_admin 角色"
    db.add(SysAccountRole(account_id=_BASE + 101, role_id=admin_role.id))
    db.add(SysAccountRole(account_id=_BASE + 102, role_id=admin_role.id))
    s1 = AiSession(id=_BASE + 1, account_id=_BASE + 101, title="我的会话")
    s2 = AiSession(id=_BASE + 2, account_id=_BASE + 102, title="他人会话")
    db.add_all([s1, s2])
    db.flush()
    db.add_all([
        AiMessage(id=_BASE + 11, session_id=s1.id, role="user", content="帮我分析Q3演练"),
        AiMessage(id=_BASE + 12, session_id=s1.id, role="assistant", content="中招率 7.5%"),
        AiMessage(id=_BASE + 13, session_id=s2.id, role="user", content="私密问题"),
    ])
    db.commit()
    yield {"mine": s1.id, "other": s2.id}
    db.query(AiMessage).filter(AiMessage.id >= _BASE).delete()
    db.query(AiSession).filter(AiSession.id >= _BASE).delete()
    db.query(SysAccountRole).filter(SysAccountRole.account_id >= _BASE).delete()
    db.query(SysAccount).filter(SysAccount.id >= _BASE).delete()
    db.commit()
    db.close()


def test_sessions_list_only_own(seeded):
    r = client.get("/api/v1/ai/sessions", headers=_token(_BASE + 101))
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1 and data[0]["id"] == seeded["mine"]


def test_messages_ordered(seeded):
    r = client.get(f"/api/v1/ai/sessions/{seeded['mine']}/messages", headers=_token(_BASE + 101))
    assert r.status_code == 200
    msgs = r.json()["data"]
    assert [m["content"] for m in msgs] == ["帮我分析Q3演练", "中招率 7.5%"]
    assert all(m["role"] in ("user", "assistant") for m in msgs)


def test_messages_isolation_404(seeded):
    # 他人会话按不存在处理（数据隔离，不泄露存在性）
    r = client.get(f"/api/v1/ai/sessions/{seeded['other']}/messages", headers=_token(_BASE + 101))
    assert r.status_code == 404


def test_messages_requires_auth(seeded):
    r = client.get(f"/api/v1/ai/sessions/{seeded['mine']}/messages")
    assert r.status_code == 401
