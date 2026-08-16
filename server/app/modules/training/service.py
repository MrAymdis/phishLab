"""安全培训服务占位（二期模块）。演练联动：SUBMIT 事件 → 自动生成培训任务。"""
from app.core.errors import BizError, ErrorCode


def list_courses(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_course(db, account, payload: dict) -> int:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_tasks(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_task(db, account, payload: dict) -> int:
    """指定人群(存快照) + 期限；source=campaign 时由演练事件触发。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_questions(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_papers(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
