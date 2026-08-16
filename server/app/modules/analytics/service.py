"""报表中心服务占位。实时指标读 Redis/汇总表，导出走异步任务。"""
from app.core.errors import BizError, ErrorCode


def overview_metrics(db, account, range_: str) -> dict:
    """数据概览：核心指标 + 方式分布 + 趋势 + TOP5 + 指纹饼图，随 range 联动。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def campaign_report(db, account, campaign_id: int) -> dict:
    """单次演练报表：漏斗（发送→打开→点击→输入→举报）+ 明细。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def department_report(db, account, range_: str) -> dict:
    """部门横向对比（stat_daily dim_type=dept）。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def trend_report(db, account, range_: str) -> dict:
    """跨演练趋势 + 场景分析。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def personal_report(db, account, user_id: int) -> dict:
    """员工个人安全档案。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def export_report(db, account, kind: str, params: dict) -> str:
    """异步导出 Excel/PDF（导出加水印），返回任务ID。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
