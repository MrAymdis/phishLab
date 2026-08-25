"""附件载荷接口测试：上传/下载/删除（服务层）+ 类型门控 + 引用保护。"""
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.campaign.models import Campaign, CampaignAttachment, CampaignStat, CampaignTarget
from app.modules.campaign.schemas import CampaignCreate
from app.modules.campaign.service import create_campaign, get_campaign
from app.modules.org.models import EmpDept, EmpUser
from app.modules.template.models import AttachmentDownloadLog, AttachmentPayload
from app.modules.template.service import delete_attachment, download_attachment, upload_attachment


@pytest.fixture(autouse=True)
def _static_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    yield tmp_path


def test_upload_download_delete(_static_tmp):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    content = b"PK\x03\x04 fake docx bytes"
    try:
        pid = upload_attachment(db, account, "发票.docx", content, platform="")
        row = db.get(AttachmentPayload, pid)
        assert row is not None
        assert row.file_type == "benign_doc"
        assert row.file_size == len(content)
        assert row.file_hash == hashlib.sha256(content).hexdigest()
        assert (Path(_static_tmp) / row.file_path).read_bytes() == content

        path, name = download_attachment(db, account, pid, ip="9.9.9.9")
        assert name == "发票.docx"
        assert Path(path).read_bytes() == content
        log = db.scalar(select(AttachmentDownloadLog)
                        .where(AttachmentDownloadLog.payload_id == pid)
                        .order_by(AttachmentDownloadLog.id.desc()))
        assert log is not None and log.action == "download" and log.ip == "9.9.9.9"

        delete_attachment(db, account, pid)
        assert db.get(AttachmentPayload, pid) is None
        assert not Path(path).exists()
    finally:
        db.close()


def test_upload_rejects_macro_exe(_static_tmp):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        with pytest.raises(BizError) as ei:
            upload_attachment(db, account, "evil.exe", b"MZ\x90\x00", platform="")
        assert "默认关闭" in ei.value.message  # 宏/EXE 载荷默认关闭，需旗舰授权（红线 6）
        with pytest.raises(BizError):
            upload_attachment(db, account, "macro.docm", b"PK", platform="")
    finally:
        db.close()


def test_delete_rejects_used(_static_tmp):
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    try:
        pid = upload_attachment(db, account, "工资条.docx", b"PK", platform="")
        c = Campaign(name="引用演练", type="mail", creator_id=1, target_mode="dept", target_snapshot={})
        db.add(c)
        db.flush()
        db.add(CampaignAttachment(campaign_id=c.id, payload_id=pid, deliver_mode="inline", sort=0))
        db.commit()

        with pytest.raises(BizError) as ei:
            delete_attachment(db, account, pid)
        assert "无法删除" in ei.value.message
        assert db.get(AttachmentPayload, pid) is not None  # 引用保护：记录保留
    finally:
        db.close()


def test_create_campaign_with_attachments(_static_tmp):
    """回归：create_campaign 带 attachment_ids 时关联生效 + used_count 累加。

    历史事故：service 漏 import CampaignAttachment 导致该路径运行时 NameError 500
    （渲染/消费测试直接建模型绕过 service，未覆盖此链路）。
    """
    db = SessionLocal()
    account = db.get(SysAccount, 1)
    cid = None
    try:
        dept = EmpDept(name="财务部", parent_id=0, path="/1/")
        db.add(dept)
        db.flush()
        user = EmpUser(name="王五", email=f"wangwu-{uuid4().hex[:6]}@corp.com", dept_id=dept.id)
        db.add(user)
        db.flush()

        pid = upload_attachment(db, account, "工资条.docx", b"PK", platform="")
        cid = create_campaign(db, account, CampaignCreate(
            name="附件回归演练", type="mail", target_mode="dept",
            target_snapshot={"dept_ids": [dept.id]},
            attachment_ids=[pid],
            auth_confirmed=True,
        ))

        rows = db.scalars(select(CampaignAttachment)
                          .where(CampaignAttachment.campaign_id == cid)).all()
        assert [r.payload_id for r in rows] == [pid]  # 关联落表
        assert db.get(AttachmentPayload, pid).used_count == 1  # 冗余计数 +1
        detail = get_campaign(db, account, cid)
        assert any(a["payload_id"] == pid for a in detail["attachments"])  # 详情回显
    finally:
        if cid:
            db.execute(delete(CampaignTarget).where(CampaignTarget.campaign_id == cid))
            db.execute(delete(CampaignStat).where(CampaignStat.campaign_id == cid))
            db.execute(delete(CampaignAttachment).where(CampaignAttachment.campaign_id == cid))
            db.execute(delete(Campaign).where(Campaign.id == cid))
        db.execute(delete(EmpUser).where(EmpUser.name == "王五"))
        db.execute(delete(EmpDept).where(EmpDept.name == "财务部"))
        db.commit()
        db.close()
