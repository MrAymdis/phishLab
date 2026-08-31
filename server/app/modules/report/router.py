from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
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
    degrade: str | None = None  # 网页邮箱合成降级原因（L2/L3），入举报备注供研判知情


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


@mail_reports.get("/plugin-config/export", summary="导出插件引导配置（含明文 API Key，下载 JSON）",
                  dependencies=[Depends(require_perm("report:classify"))])
def export_plugin_config(request: Request, base: str | None = Query(default=None),
                         account=Depends(get_current_account), db: Session = Depends(get_db)):
    """配置文件直出（非统一响应包裹）：Content-Disposition 附件供插件客户端导入。

    base 由前端传 location.origin：反代（vite/nginx）改写 Host 时 request.base_url 不可达。
    """
    base_url = (base or str(request.base_url)).strip()
    if not base_url.startswith(("http://", "https://")):
        raise BizError(ErrorCode.PARAM_INVALID, "base 参数必须是 http(s) 绝对地址")
    cfg = service.export_plugin_config(db, account, base_url)
    return JSONResponse(cfg, headers={
        "Content-Disposition": 'attachment; filename="phishlab-plugin-config.json"',
    })


@plugin.post("/mail", summary="举报插件上报（Outlook/Webmail，X-Api-Key 鉴权）")
def plugin_report(payload: PluginReport, x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
                  db: Session = Depends(get_db)):
    if not service.verify_plugin_key(db, x_api_key):
        raise BizError(ErrorCode.UNAUTHORIZED, "插件 API Key 无效或未配置")
    return resp.ok({"id": service.ingest_from_plugin(db, payload.model_dump())})


# ---------- 举报邮件归档（EML 预览/下载，数据权限与列表同口径） ----------

@mail_reports.get("/{rid}/preview", summary="举报邮件预览（从 EML 归档解析）")
def preview(rid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.report_preview(db, account, rid))


@mail_reports.get("/{rid}/eml", summary="下载举报邮件 EML 原件")
def download_eml(rid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    path = service.report_eml_path(db, account, rid)
    if path is None:
        raise BizError(ErrorCode.NOT_FOUND, "该举报无 EML 归档（Web 邮箱/旧版客户端仅上报元数据）")
    return FileResponse(str(path), media_type="message/rfc822", filename=f"report-{rid}.eml")


# ---------- 插件资产托管（公开：taskpane/图标/安装包须无鉴权可达） ----------

@plugin.get("/plugin/outlook/manifest.xml", summary="Outlook Web Add-in manifest（动态注入 base URL）")
def outlook_manifest(request: Request, base: str | None = Query(default=None)):
    """base 由前端传 location.origin：反代改写 Host 时 request.base_url 对客户不可达。

    Outlook 硬性要求 manifest 内所有 URL 为 https://（自签证书可用，http 连 localhost 都不豁免），
    因此拒绝 http base 直接失败，避免生成一份必然装不上的 manifest。
    """
    base_url = (base or str(request.base_url)).strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise BizError(ErrorCode.PARAM_INVALID,
                       "Outlook 加载项要求 manifest 内所有 URL 必须为 https:// 地址"
                       "（http 连 localhost 都不豁免），请通过 https 访问管理端重新下载")
    # 必须带 Content-Disposition：前端下载助手据此落名，Outlook 添加自定义加载项只认 .xml
    return Response(service.build_outlook_manifest(base_url), media_type="application/xml",
                    headers={"Content-Disposition": 'attachment; filename="phishlab-outlook-manifest.xml"'})


@plugin.get("/plugin/webmail.zip", summary="Web 邮箱举报扩展安装包（zip 运行时打包）")
def webmail_zip():
    return Response(service.build_webmail_zip(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="phishlab-webmail-plugin.zip"'})


@plugin.get("/plugin/{file_path:path}", include_in_schema=False)
def plugin_static(file_path: str):
    root = service.PLUGIN_ASSETS_DIR.resolve()
    target = (root / file_path).resolve()
    # 路径穿越防护：目标必须位于插件资产目录内
    if root not in target.parents or not target.is_file():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse(str(target), headers={"Cache-Control": "no-cache"})
