"""AI 服务占位（三期模块）。SSE 帧协议：{type: token|action|done|error}。

硬约束：AI 产出一律进 ai_draft 草稿态，人工 approve 后入库；审核记录入审计。
"""
from app.core.errors import BizError, ErrorCode


def list_sessions(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def chat_stream(db, account, payload: dict):
    """Copilot 对话：LLM 适配层 + 页面上下文；返回 async generator 供 SSE。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def generate_template(db, account, payload: dict) -> int:
    """AI 模板生成 → ai_draft(biz_type=email_template)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def generate_analysis(db, account, kind: str, target: dict) -> int:
    """智能分析报告（演练效果/部门画像/趋势预测/培训建议）→ ai_draft。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_drafts(db, account, status: str | None = None):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def approve_draft(db, account, draft_id: int) -> dict:
    """确认入库：按 biz_type 写入目标表，回填 biz_id，记录审核人/时间。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def discard_draft(db, account, draft_id: int):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
