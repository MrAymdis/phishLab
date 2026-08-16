from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
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
    display_name: str | None = None
    from_addr: str | None = None
    reply_to: str | None = None
    sms_number: str | None = None
    sms_sign: str | None = None
    scene_tags: list[str] = []


@channels.get("", summary="通道列表")
def list_channels(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_channels(db, account))


@channels.post("", summary="添加发送配置（SMTP/EWS/SMS）")
def create_channel(payload: ChannelCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_channel(db, account, payload.model_dump())})


@channels.post("/{cid}/test", summary="通道连通测试")
def test_channel(cid: int, to: str | None = None, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.test_channel(db, account, cid, to))


@domains.get("", summary="演练域名列表（含 DNS 状态/送达评分）")
def list_domains(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_domains(db, account))


@domains.post("", summary="添加演练域名（生成 DKIM/DNS 指引）")
def add_domain(payload: DomainCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.add_domain(db, account, payload.model_dump())})


@domains.get("/{did}/dns-check", summary="DNS 检测 + 送达评分")
def dns_check(did: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.check_dns(db, account, did))


@sender_profiles.get("", summary="伪装发件人列表")
def list_profiles(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_sender_profiles(db, account))


@sender_profiles.post("", summary="新建伪装发件人")
def create_profile(payload: SenderProfileCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_sender_profile(db, account, payload.model_dump())})
