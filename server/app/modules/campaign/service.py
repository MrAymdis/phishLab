"""演练服务：脚手架阶段为占位实现，方法签名即一期待办清单。

实现要点见《架构设计方案》§3.2：状态机、发送管线、追踪事件、预警。
"""
from app.core.errors import BizError, ErrorCode


def list_campaigns(db, account, *, status=None, type=None, kw=None, page=1, page_size=20):
    """列表 + 统计卡片：读 campaign + campaign_stat，强制 apply_data_scope。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def get_campaign(db, account, campaign_id: int):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_campaign(db, account, payload) -> int:
    """校验(授权勾选/通道/域名DNS/模板审核) → 目标展开 → 生成 target+token → 切批次。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def update_draft(db, account, campaign_id: int, payload):
    """向导草稿暂存（仅 status=draft 可编辑）。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def start(db, account, campaign_id: int):
    """draft/scheduled → sending：写入批次调度（Celery）。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def pause(db, account, campaign_id: int):
    """running → paused：停止批次调度，追踪继续。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def resume(db, account, campaign_id: int):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def terminate(db, account, campaign_id: int):
    """任意非终态 → terminated：停止发送与追踪，写审计。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def dashboard(db, account, campaign_id: int) -> dict:
    """指标卡 + 漏斗：读 Redis 计数（降级 campaign_stat）。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def timeline(db, account, campaign_id: int, page: int, page_size: int):
    """用户行为时间轴：track_event join emp_user，附 IP/UA/指纹。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def test_send(db, account, campaign_id: int, to: list[str]):
    """发送测试：仅白名单收件人。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
