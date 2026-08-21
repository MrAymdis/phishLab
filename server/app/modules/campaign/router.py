from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.core.pagination import page_params
from app.db.session import get_db

from . import schemas, service

campaigns = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["演练管理"],
    dependencies=[Depends(get_current_account), Depends(require_perm("menu:/campaign"))],
)
routers = [campaigns]


@campaigns.get("", summary="演练列表（统计卡片 + 筛选）")
def list_campaigns(
    status: str | None = Query(None, description="draft/scheduled/sending/running/paused/completed/terminated"),
    type: str | None = Query(None, alias="type", description="mail/sms/social/usb"),
    kw: str | None = None,
    start_date: str | None = Query(None, description="时间范围起 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="时间范围止 YYYY-MM-DD"),
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.list_campaigns(
        db, account, status=status, type=type, kw=kw,
        start_date=start_date, end_date=end_date, page=page, page_size=page_size,
    ))


@campaigns.post("", summary="创建演练（7步向导）", dependencies=[Depends(require_perm("campaign:create"))])
def create(payload: schemas.CampaignCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_campaign(db, account, payload)})


@campaigns.get("/{cid}", summary="演练详情")
def detail(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_campaign(db, account, cid))


@campaigns.post("/{cid}/duplicate", summary="复制演练（生成新草稿）", dependencies=[Depends(require_perm("campaign:create"))])
def duplicate(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.duplicate_campaign(db, account, cid)})


@campaigns.delete("/{cid}", summary="删除演练（仅草稿/已终止）", dependencies=[Depends(require_perm("campaign:delete"))])
def delete(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_campaign(db, account, cid))


@campaigns.put("/{cid}/draft", summary="向导草稿暂存", dependencies=[Depends(require_perm("campaign:control"))])
def save_draft(cid: int, payload: schemas.CampaignCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_draft(db, account, cid, payload))


@campaigns.post("/{cid}/start", summary="启动", dependencies=[Depends(require_perm("campaign:control"))])
def start(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.start(db, account, cid))


@campaigns.post("/{cid}/pause", summary="暂停", dependencies=[Depends(require_perm("campaign:control"))])
def pause(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.pause(db, account, cid))


@campaigns.post("/{cid}/resume", summary="恢复", dependencies=[Depends(require_perm("campaign:control"))])
def resume(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.resume(db, account, cid))


@campaigns.post("/{cid}/terminate", summary="终止", dependencies=[Depends(require_perm("campaign:control"))])
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


@campaigns.post("/{cid}/events/{event_id}/reveal", summary="取证：操作密码验证后解密全部明文（全程审计）",
                dependencies=[Depends(require_perm("campaign:reveal"))])
def reveal_password(
    cid: int,
    event_id: int,
    payload: dict = Body(...),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    op = str(payload.get("operation_password") or "")
    return resp.ok(service.reveal_submit_password(db, account, cid, event_id, op))


@campaigns.api_route("/{cid}/stream", methods=["GET", "POST"], summary="实时推送（SSE）")
async def stream(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    """演练详情实时推送：快照 + Redis 事件订阅（追踪事件由 Worker 落库后 publish）。"""
    from app.modules.campaign.sse import campaign_event_stream

    return EventSourceResponse(campaign_event_stream(db, account, cid))


@campaigns.post("/{cid}/test-send", summary="发送测试", dependencies=[Depends(require_perm("campaign:control"))])
def test_send(cid: int, to: list[str], account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.test_send(db, account, cid, to))
