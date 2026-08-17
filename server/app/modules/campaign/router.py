import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import response as resp
from app.core.deps import get_current_account
from app.core.errors import BizError, ErrorCode
from app.core.pagination import page_params
from app.db.session import get_db

from . import schemas, service

campaigns = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["演练管理"],
    dependencies=[Depends(get_current_account)],
)
routers = [campaigns]


@campaigns.get("", summary="演练列表（统计卡片 + 筛选）")
def list_campaigns(
    status: str | None = Query(None, description="draft/scheduled/sending/running/paused/completed/terminated"),
    type: str | None = Query(None, alias="type", description="mail/sms/social/usb"),
    kw: str | None = None,
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.list_campaigns(db, account, status=status, type=type, kw=kw, page=page, page_size=page_size))


@campaigns.post("", summary="创建演练（7步向导）")
def create(payload: schemas.CampaignCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_campaign(db, account, payload)})


@campaigns.get("/{cid}", summary="演练详情")
def detail(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_campaign(db, account, cid))


@campaigns.put("/{cid}/draft", summary="向导草稿暂存")
def save_draft(cid: int, payload: schemas.CampaignCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_draft(db, account, cid, payload))


@campaigns.post("/{cid}/start", summary="启动")
def start(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.start(db, account, cid))


@campaigns.post("/{cid}/pause", summary="暂停")
def pause(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.pause(db, account, cid))


@campaigns.post("/{cid}/resume", summary="恢复")
def resume(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.resume(db, account, cid))


@campaigns.post("/{cid}/terminate", summary="终止")
def terminate(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.terminate(db, account, cid))


@campaigns.get("/{cid}/dashboard", summary="监控大屏：指标卡 + 漏斗")
def dashboard(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.dashboard(db, account, cid))


@campaigns.get("/{cid}/timeline", summary="用户行为时间轴")
def timeline(
    cid: int,
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.timeline(db, account, cid, page, page_size))


@campaigns.get("/{cid}/stream", summary="实时推送（SSE）")
async def stream(cid: int):
    async def gen():
        # TODO(一期)：订阅 Redis 事件 → 推送指标增量与时间轴新事件
        yield {"event": "message", "data": json.dumps(
            {"type": "error", "code": ErrorCode.NOT_IMPLEMENTED, "message": "实时推送尚未实现"},
            ensure_ascii=False,
        )}

    return EventSourceResponse(gen())


@campaigns.post("/{cid}/test-send", summary="发送测试")
def test_send(cid: int, to: list[str], account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.test_send(db, account, cid, to))


@campaigns.delete("/{cid}", summary="删除演练（仅草稿）")
def delete_campaign(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.delete_campaign(db, account, cid)
    return resp.ok({"id": cid})
