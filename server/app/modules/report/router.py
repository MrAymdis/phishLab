from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.core.errors import BizError, ErrorCode
from app.core.pagination import page_params
from app.db.session import get_db

from . import service

mail_reports = APIRouter(prefix="/api/v1/mail-reports", tags=["邮件举报"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/mail-report"))])
plugin = APIRouter(prefix="/report/v1", tags=["邮件举报-插件"])  # 插件端点：X-Api-Key 独立鉴权
routers = [mail_reports, plugin]


class ClassifyRequest(BaseModel):
    classification: str  # drill/real_phishing/false_positive/spam
    remark: str | None = None


class PluginReport(BaseModel):
    channel: str = "outlook_plugin"
    reporter_email: str | None = None
    message_id: str | None = None
    from_addr: str | None = None
    subject: str | None = None
    headers: str | None = None
    eml_base64: str | None = None


class RewardRulesRequest(BaseModel):
    rules: list[dict]


class PluginConfigRequest(BaseModel):
    allowedDomains: list[str] = []
    webhookUrl: str = ""
    autoclass: bool = True
    notifyChannels: dict = {}


class RedeemRequest(BaseModel):
    user_id: int
    item_id: int


@mail_reports.get("", summary="举报列表（分类/关键词/时间筛选）")
def list_reports(
    classification: str | None = None,
    kw: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.list_reports(db, account, classification=classification,
                                        page=page, page_size=page_size,
                                        kw=kw, start_date=start_date, end_date=end_date))


@mail_reports.get("/stats", summary="举报中心统计卡 + 分类计数")
def stats(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.report_stats(db))


@mail_reports.post("/{rid}/classify", summary="人工研判", dependencies=[Depends(require_perm("report:classify"))])
def classify(rid: int, req: ClassifyRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.classify(db, account, rid, req.classification, req.remark))


# ---------- 举报奖励 ----------

@mail_reports.get("/ranking", summary="积分排行榜（本月 + 累计 TOP20）")
def ranking(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.ranking(db))


@mail_reports.get("/points/overview", summary="平台积分概览 + 最近兑换记录")
def points_overview(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.points_overview(db))


@mail_reports.get("/reward-rules", summary="积分规则（可编辑）")
def reward_rules(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"rules": service.get_reward_rules(db)})


@mail_reports.put("/reward-rules", summary="保存积分规则", dependencies=[Depends(require_perm("report:classify"))])
def update_reward_rules(req: RewardRulesRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"rules": service.update_reward_rules(db, account, req.rules)})


@mail_reports.get("/reward-catalog", summary="兑换商品目录")
def reward_catalog(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"items": service.reward_catalog(db)})


@mail_reports.post("/redeem", summary="员工积分兑换", dependencies=[Depends(require_perm("report:classify"))])
def redeem(req: RedeemRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.redeem(db, account, req.user_id, req.item_id))


# ---------- 插件配置 ----------

@mail_reports.get("/plugin-config", summary="插件 API 配置（Key 掩码回显）")
def plugin_config(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_plugin_config(db))


@mail_reports.put("/plugin-config", summary="保存插件配置", dependencies=[Depends(require_perm("report:classify"))])
def update_plugin_config(req: PluginConfigRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_plugin_config(db, account, req.model_dump()))


@mail_reports.post("/plugin-config/regen-key", summary="重生成插件 API Key",
                   dependencies=[Depends(require_perm("report:classify"))])
def regen_plugin_key(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.regenerate_plugin_key(db, account))


@mail_reports.post("/plugin-config/test-webhook", summary="Webhook 测试连接",
                   dependencies=[Depends(require_perm("report:classify"))])
def test_webhook(req: dict | None = None, account=Depends(get_current_account), db: Session = Depends(get_db)):
    webhook = (req or {}).get("webhookUrl")
    return resp.ok(service.test_plugin_webhook(db, webhook))


@plugin.post("/mail", summary="举报插件上报（Outlook/Webmail，X-Api-Key 鉴权）")
def plugin_report(payload: PluginReport, x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
                  db: Session = Depends(get_db)):
    if not service.verify_plugin_key(db, x_api_key):
        raise BizError(ErrorCode.UNAUTHORIZED, "插件 API Key 无效或未配置")
    return resp.ok({"id": service.ingest_from_plugin(db, payload.model_dump())})
