"""AI 生成扩展测试（HTTP 全链路）：落地页 / 企微消息 / 诱饵文档 + 邮件自定义场景。

- 生成一律进 ai_draft（草稿硬约束），approve 后按 biz_type 入库；
- 诱饵文档 approve 渲染真实文件写入附件库（pdf/xlsx 良性，宏/EXE 不开放）；
- 邮件自定义场景字符串原样透传（approve 后 EmailTemplate.scene == 自定义值）。
"""
import datetime
import io
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select as sa_select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app

_BASE = 9700

client = TestClient(app)


def _token(account_id: int) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"Authorization": "Bearer " + jwt.encode(
        {"sub": str(account_id), "username": f"t{account_id}", "iat": now,
         "exp": now + datetime.timedelta(minutes=60)},
        settings.secret_key, algorithm="HS256",
    )}


@pytest.fixture()
def seeded(monkeypatch):
    """测试账号挂 super_admin（router 级菜单权限直通）+ 禁用真实 LLM（确定性走本地降级）。"""
    from app.modules.account.models import SysAccount
    from app.modules.ai import service as ai_service
    from app.modules.rbac.models import SysAccountRole, SysRole

    monkeypatch.setattr(ai_service, "get_provider", lambda db: None)

    db = SessionLocal()
    db.add(SysAccount(id=_BASE + 101, username=f"aigen{_BASE}", password_hash="x",
                      real_name="AI生成测试", status=1))
    admin_role = db.scalar(sa_select(SysRole).where(SysRole.code == "super_admin"))
    assert admin_role is not None, "种子数据缺少 super_admin 角色"
    db.add(SysAccountRole(account_id=_BASE + 101, role_id=admin_role.id))
    db.commit()
    yield {"uid": _BASE + 101}
    # 清理：AI 草稿 + 各素材表（附件文件单独清）
    from app.modules.ai.models import AiDraft
    from app.modules.template.models import (AttachmentPayload, EmailTemplate,
                                             LandingFormField, LandingPage, WecomTemplate)

    files = db.scalars(
        sa_select(AttachmentPayload.file_path).where(AttachmentPayload.created_by == _BASE + 101)
    ).all()
    # 表单字段无 created_by，按所属落地页先删（SQLite 无级联）
    page_ids = db.scalars(sa_select(LandingPage.id).where(LandingPage.created_by == _BASE + 101)).all()
    if page_ids:
        db.execute(LandingFormField.__table__.delete().where(LandingFormField.page_id.in_(page_ids)))
    for table in (AttachmentPayload, EmailTemplate, LandingPage, WecomTemplate, AiDraft):
        db.execute(table.__table__.delete().where(table.created_by == _BASE + 101))
    db.execute(SysAccountRole.__table__.delete().where(SysAccountRole.account_id >= _BASE))
    db.execute(SysAccount.__table__.delete().where(SysAccount.id >= _BASE))
    db.commit()
    db.close()
    for rel in files:  # 附件物理文件清理（静态目录）
        (Path(settings.static_dir) / rel).unlink(missing_ok=True)


def _gen(path: str, body: dict, seeded) -> int:
    r = client.post(path, json=body, headers=_token(seeded["uid"]))
    assert r.status_code == 200 and r.json()["code"] == 0, r.text
    return r.json()["data"]["draft_id"]


def _approve(seeded, draft_id: int) -> dict:
    r = client.post(f"/api/v1/ai/drafts/{draft_id}/approve", headers=_token(seeded["uid"]))
    assert r.status_code == 200 and r.json()["code"] == 0, r.text
    return r.json()["data"]


def test_landing_generate_approve(seeded):
    from app.modules.template.models import LandingFormField, LandingPage

    did = _gen("/api/v1/ai/landings/generate", {"scene": "mail", "company": "测试科技"}, seeded)
    data = _approve(seeded, did)
    assert data["biz_id"], "确认入库未回填 biz_id"

    db = SessionLocal()
    page = db.scalar(sa_select(LandingPage).where(LandingPage.id == data["biz_id"]))
    assert page is not None
    assert page.source == "ai", "AI 产出落地页来源须标记 ai"
    assert page.type == "mail_login"
    assert page.slug and page.html_content
    fields = db.scalars(sa_select(LandingFormField).where(LandingFormField.page_id == page.id)).all()
    assert {f.label for f in fields} >= {"用户名", "密码"}
    db.close()


def test_wecom_generate_approve(seeded):
    from app.modules.template.models import WecomTemplate

    did = _gen("/api/v1/ai/wecoms/generate", {"scene": "system", "audience": "财务部"}, seeded)
    data = _approve(seeded, did)

    db = SessionLocal()
    tpl = db.scalar(sa_select(WecomTemplate).where(WecomTemplate.id == data["biz_id"]))
    assert tpl is not None
    assert tpl.status == "approved", "AI 草稿确认后应为已审核状态"
    assert tpl.msg_type == "textcard" and tpl.title and tpl.description
    db.close()


def test_attachment_docx_approve_renders_file(seeded):
    import zipfile

    from app.modules.template.models import AttachmentPayload

    did = _gen("/api/v1/ai/attachments/generate",
               {"scene": "补贴通知", "audience": "全体员工", "doc_type": "docx"}, seeded)
    data = _approve(seeded, did)

    db = SessionLocal()
    p = db.scalar(sa_select(AttachmentPayload).where(AttachmentPayload.id == data["biz_id"]))
    assert p is not None
    assert p.file_type == "benign_doc", "AI 文档属良性附件（红线 6：不产出宏/EXE）"
    assert p.platform == "AI生成"
    abs_path = Path(settings.static_dir) / p.file_path
    assert abs_path.is_file() and abs_path.stat().st_size > 0
    assert abs_path.read_bytes()[:2] == b"PK", "应渲染为真实 docx（OOXML zip）文件"
    # beacon 就绪：投递链路 _render_docx_variant 依赖 document.xml.rels 注入 /pa/ 外链关系
    with zipfile.ZipFile(abs_path) as z:
        names = z.namelist()
        assert "word/document.xml" in names and "word/_rels/document.xml.rels" in names
        assert "补贴通知" in z.read("word/document.xml").decode("utf-8")
        assert "{{.FirstName}}" in z.read("word/document.xml").decode("utf-8"), \
            "占位符应保留供投递时个性化替换"
    db.close()


def test_attachment_xlsx_approve_renders_file(seeded):
    from app.modules.template.models import AttachmentPayload

    did = _gen("/api/v1/ai/attachments/generate",
               {"scene": "工资明细", "audience": "财务部", "doc_type": "xlsx"}, seeded)
    data = _approve(seeded, did)

    db = SessionLocal()
    p = db.scalar(sa_select(AttachmentPayload).where(AttachmentPayload.id == data["biz_id"]))
    assert p is not None
    abs_path = Path(settings.static_dir) / p.file_path
    assert abs_path.is_file() and abs_path.read_bytes()[:2] == b"PK", "应渲染为真实 xlsx 文件"
    db.close()


def test_ai_docx_accepts_beacon_injection(seeded):
    """跨模块契约：AI 生成的 docx 必须能被投递链路注入 /pa/ beacon 并做占位符个性化。

    注入后 beacon 外链关系应出现在 word/_rels/document.xml.rels，
    且 document.xml 内含 rIdPhishLabBeacon 引用（附件运行追踪 attach_run 的前提）。
    """
    import zipfile

    from app.modules.campaign.render import _render_docx_variant

    did = _gen("/api/v1/ai/attachments/generate",
               {"scene": "会议邀请", "audience": "管理层", "doc_type": "docx"}, seeded)
    data = _approve(seeded, did)

    from app.modules.template.models import AttachmentPayload

    db = SessionLocal()
    p = db.scalar(sa_select(AttachmentPayload).where(AttachmentPayload.id == data["biz_id"]))
    abs_path = Path(settings.static_dir) / p.file_path
    raw = abs_path.read_bytes()
    db.close()

    variant = _render_docx_variant(raw, {"{{.FirstName}}": "张三"},
                                   "http://track.example/pa/tok123.png")
    assert variant != raw, "beacon 注入后文件内容应变化"
    with zipfile.ZipFile(io.BytesIO(variant)) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "rIdPhishLabBeacon" in doc, "正文应引用 beacon 图片关系"
    assert "/pa/tok123.png" in rels, "关系文件应指向 /pa/ 追踪端点"
    assert "张三" in doc and "{{.FirstName}}" not in doc, "占位符应被个性化替换"


def test_attachment_bad_doc_type_rejected(seeded):
    for bad in ("exe", "pdf"):
        r = client.post("/api/v1/ai/attachments/generate",
                        json={"scene": "通知", "doc_type": bad}, headers=_token(seeded["uid"]))
        assert r.json()["code"] != 0, f"不支持的文档类型 {bad} 应被拒绝（红线 6/白名单）"


def test_email_custom_scene_passthrough(seeded):
    from app.modules.template.models import EmailTemplate

    did = _gen("/api/v1/ai/templates/generate", {"scene": "供应商对账", "audience": "采购部"}, seeded)
    data = _approve(seeded, did)

    db = SessionLocal()
    tpl = db.scalar(sa_select(EmailTemplate).where(EmailTemplate.id == data["biz_id"]))
    assert tpl is not None
    assert tpl.scene == "供应商对账", "自定义场景应原样透传到模板"
    assert tpl.source == "ai" and tpl.html_body
    db.close()
