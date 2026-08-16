"""邮件举报服务占位（二期模块）。

插件上报 → 自动识别（匹配 Message-ID/token/发件域）→ drill / real_phishing → 研判闭环。
"""
from app.core.errors import BizError, ErrorCode


def list_reports(db, account, *, classification=None, page=1, page_size=20):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def classify(db, account, report_id: int, classification: str, remark: str | None = None):
    """人工研判：drill/real_phishing/false_positive/spam；真实钓鱼联动 SIEM 推送。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def ingest_from_plugin(db, payload: dict) -> int:
    """插件上报入口（独立鉴权）：存 eml → 自动分类 → 积分规则。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
