"""审计日志写入辅助。所有写操作（含 AI 审核、导出、载荷下载）必须留痕。"""
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("phishlab.audit")


def record_audit(
    db: Session,
    *,
    account,
    module: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    from app.modules.rbac.models import AuditLog  # 延迟导入避免循环

    try:
        db.add(
            AuditLog(
                account_id=getattr(account, "id", None),
                account_name=getattr(account, "real_name", None) or getattr(account, "username", None),
                module=module,
                action=action,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                detail=detail,
                ip=ip,
            )
        )
        db.commit()
    except Exception:  # 审计失败不阻断业务，但必须可感知
        db.rollback()
        logger.exception("审计写入失败 module=%s action=%s", module, action)
