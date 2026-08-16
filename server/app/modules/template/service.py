"""素材模板服务占位。实现要点见《架构设计方案》§3.3 模板中心。"""
from app.core.errors import BizError, ErrorCode


def list_email_templates(db, account, scene=None):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_email_template(db, account, payload: dict) -> int:
    """富文本 + 变量解析 {{.FirstName}} 等；AI 来源进 ai_draft 审核流。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def test_send_template(db, account, template_id: int, to: list[str]):
    """模板测试发送：仅限白名单账号。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_landing_pages(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_landing_page(db, account, payload: dict) -> int:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def clone_url(db, account, url: str) -> int:
    """URL 克隆：抓取 → 重写表单 action 至 /p/{slug}/submit → 去除外部资源。

    红线：仅允许克隆客户自有/已授权系统页面，操作必须留审计。TODO(二期)。
    """
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_attachments(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_qr_assets(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
