from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service

channels = APIRouter(prefix="/api/v1/channels", tags=["发送配置"], dependencies=[Depends(get_current_account)])
domains = APIRouter(prefix="/api/v1/domains", tags=["发送配置"], dependencies=[Depends(get_current_account)])
sender_profiles = APIRouter(prefix="/api/v1/sender-profiles", tags=["发送配置"], dependencies=[Depends(get_current_account)])
routers = [channels, domains, sender_profiles]


class ChannelCreate(BaseModel):
    name: str
    type: str  # smtp/ews/sms
    daily_limit: int = 5000
    is_default: bool = False
    # 其余字段按 type 分组，见 models.SendChannel；此处开放 dict
    config: dict = {}


class DomainCreate(BaseModel):
    domain: str
    purpose: str | None = None


class SenderProfileCreate(BaseModel):
    name: str
    channel_type: str  # mail/sms
    channel_id: int | None = None  # 关联发送通道，空=用默认SMTP通道
    display_name: str | None = None
    from_addr: str | None = None
    reply_to: str | None = None
    sms_number: str | None = None
    sms_sign: str | None = None
    scene_tags: list[str] = []


@channels.get("", summary="通道列表")
def list_channels(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_channels(db, account))


@channels.get("/overview", summary="发送配置概览（本月发送总量）")
def channel_overview(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.channel_overview(db, account))


@channels.post("", summary="添加发送配置（SMTP/EWS/SMS）", dependencies=[Depends(require_perm("channel:manage"))])
def create_channel(payload: ChannelCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_channel(db, account, payload.model_dump())})


@channels.put("/{cid}", summary="更新发送配置（敏感字段留空则沿用已有密文）", dependencies=[Depends(require_perm("channel:manage"))])
def update_channel(cid: int, payload: ChannelCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_channel(db, account, cid, payload.model_dump()))


@channels.delete("/{cid}", summary="删除发送配置", dependencies=[Depends(require_perm("channel:manage"))])
def delete_channel(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_channel(db, account, cid))


@channels.post("/{cid}/test", summary="通道连通测试")
def test_channel(cid: int, to: str | None = None, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.test_channel(db, account, cid, to))


class SendTestRequest(BaseModel):
    to: str


class DraftSendTestRequest(BaseModel):
    """弹窗中尚未保存的通道配置直接发测试邮件（不落库）。"""
    to: str
    name: str | None = None
    type: str = "smtp"
    config: dict = {}


class ContentSendTestRequest(BaseModel):
    """演练向导预览发送：模板 + 落地页 + 伪装发件人的真实样式测试邮件。"""
    to: str
    template_id: int | None = None
    landing_page_id: int | None = None
    sender_name: str | None = None
    domain: str | None = None  # 欺骗性域名（链接域名，与真实演练邮件一致）


@channels.post("/send-test", summary="用未保存的通道配置发送测试邮件（不落库）", dependencies=[Depends(require_perm("channel:manage"))])
def send_test_email_draft(req: DraftSendTestRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.send_test_email_draft(db, account, req.model_dump()))


@channels.post("/{cid}/send-test-email", summary="发送模板+落地页样式的演练预览测试邮件", dependencies=[Depends(require_perm("channel:manage"))])
def send_test_email_with_content(cid: int, req: ContentSendTestRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.send_test_email_with_content(db, account, cid, req.model_dump()))


@channels.post("/{cid}/send-test", summary="发送测试邮件（真实 SMTP 发信）", dependencies=[Depends(require_perm("channel:manage"))])
def send_test_email(cid: int, req: SendTestRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.send_test_email(db, account, cid, req.to))


@domains.get("", summary="演练域名列表（含 DNS 状态/送达评分）")
def list_domains(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_domains(db, account))


@domains.post("", summary="添加演练域名（生成 DKIM/DNS 指引）", dependencies=[Depends(require_perm("channel:manage"))])
def add_domain(payload: DomainCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.add_domain(db, account, payload.model_dump())})


@domains.get("/{did}/dns-check", summary="DNS 检测 + 送达评分")
def dns_check(did: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.check_dns(db, account, did))


@domains.delete("/{did}", summary="删除域名", dependencies=[Depends(require_perm("channel:manage"))])
def delete_domain(did: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.delete_domain(db, account, did)
    return resp.ok({"id": did})


@sender_profiles.get("", summary="伪装发件人列表")
def list_profiles(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_sender_profiles(db, account))


@sender_profiles.post("", summary="新建伪装发件人", dependencies=[Depends(require_perm("channel:manage"))])
def create_profile(payload: SenderProfileCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_sender_profile(db, account, payload.model_dump())})


@sender_profiles.put("/{pid}", summary="更新伪装发件人", dependencies=[Depends(require_perm("channel:manage"))])
def update_profile(pid: int, payload: SenderProfileCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.update_sender_profile(db, account, pid, payload.model_dump())})


@sender_profiles.delete("/{pid}", summary="删除伪装发件人（被演练引用时拒绝）", dependencies=[Depends(require_perm("channel:manage"))])
def delete_profile(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.delete_sender_profile(db, account, pid)
    return resp.ok({"id": pid})


class SenderProfileTest(BaseModel):
    to: str


@sender_profiles.post("/{pid}/test-send", summary="用伪装发件人通过默认 SMTP 通道发送测试邮件", dependencies=[Depends(require_perm("channel:manage"))])
def test_profile(pid: int, payload: SenderProfileTest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.test_sender_profile(db, account, pid, payload.to))
