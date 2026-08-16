"""邮件举报服务：插件上报 → 自动分类（发件人/伪造域名匹配）→ 人工研判闭环。

演练命中（drill）即时发举报积分；真实钓鱼研判后 TODO(二期) 联动 SIEM。
"""
from datetime import datetime

from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode
from app.modules.channel.models import SenderProfile
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser

from .models import MailReport, ReportRewardLog

VALID_CLASSIFICATION = ("drill", "real_phishing", "false_positive", "spam")
# 列表「自动识别/人工研判」两列的展示映射
_CLASS_MAP = {"drill": "drill", "real_phishing": "real", "false_positive": "false", "spam": "false", "pending": ""}
DRILL_DOMAIN = "drill.phishlab.cn"


def list_reports(db, account, *, classification=None, page=1, page_size=20):
    """举报列表：分类筛选 + 分页；补充举报人/部门信息（批量查询避免 N+1）。"""
    count_stmt = select(func.count()).select_from(MailReport)
    stmt = select(MailReport).order_by(MailReport.id.desc())
    if classification:
        count_stmt = count_stmt.where(MailReport.classification == classification)
        stmt = stmt.where(MailReport.classification == classification)
    total = int(db.scalar(count_stmt) or 0)
    reports = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    # 批量补员工/部门
    user_ids = {r.reporter_user_id for r in reports if r.reporter_user_id}
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    items = []
    for r in reports:
        user = users.get(r.reporter_user_id)
        mapped = _CLASS_MAP.get(r.classification, "")
        items.append({
            "id": r.id,
            "time": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            "subject": r.subject or "",
            "sender": r.from_addr or "",
            "reporter": (user.name if user else None) or r.reporter_email or "",
            "reporterDept": depts[user.dept_id].name if user and user.dept_id in depts else "",
            "auto": mapped,
            "manual": mapped if r.classifier == "manual" else "",
            "remark": r.handle_remark or "",
        })
    return {"list": items, "total": total, "page": page, "pageSize": page_size}


def classify(db, account, report_id: int, classification: str, remark: str | None = None):
    """人工研判：drill/real_phishing/false_positive/spam；演练命中发积分，真实钓鱼 TODO SIEM。"""
    if classification not in VALID_CLASSIFICATION:
        raise BizError(ErrorCode.PARAM_INVALID)
    report = db.get(MailReport, report_id)
    if report is None:
        raise BizError(ErrorCode.NOT_FOUND)

    report.classification = classification
    report.classifier = "manual"
    report.handler_id = account.id
    report.handled_at = datetime.now()
    report.handle_remark = remark

    if classification == "drill":
        # 演练举报：积分入账 + 风险画像举报意识加分
        report.reward_points = 10
        if report.reporter_user_id:
            db.add(ReportRewardLog(user_id=report.reporter_user_id, report_id=report.id,
                                   points=10, reason="演练邮件举报"))
            profile = db.get(EmpRiskProfile, report.reporter_user_id)
            if profile is None:  # 无画像则初始化
                profile = EmpRiskProfile(user_id=report.reporter_user_id, total_score=50)
                db.add(profile)
            profile.report_count = int(profile.report_count or 0) + 1
    elif classification == "real_phishing":
        pass  # TODO(二期)：SIEM 推送

    db.commit()
    record_audit(db, account=account, module="report", action="classify",
                 target_id=str(report_id), detail={"classification": classification})
    return {"id": report_id, "classification": classification}


def ingest_from_plugin(db, payload: dict) -> int:
    """插件上报入口（独立鉴权）：落库 → 自动分类 → 演练命中即时发积分。"""
    from_addr = payload.get("from_addr")
    reporter_email = payload.get("reporter_email")

    # 自动分类：演练域名后缀或已配置伪装发件人 → drill；其余默认真实钓鱼待研判
    classification = "real_phishing"
    if from_addr:
        if from_addr.lower().endswith(DRILL_DOMAIN):
            classification = "drill"
        elif db.scalar(
            select(func.count()).select_from(SenderProfile)
            .where(func.lower(SenderProfile.from_addr) == from_addr.lower())
        ):
            classification = "drill"

    reporter_user_id = None
    if reporter_email:
        user = db.scalar(select(EmpUser).where(EmpUser.email == reporter_email))
        reporter_user_id = user.id if user else None

    report = MailReport(
        channel=payload.get("channel") or "outlook_plugin",
        reporter_user_id=reporter_user_id,
        reporter_email=reporter_email,
        message_id=payload.get("message_id"),
        from_addr=from_addr,
        subject=payload.get("subject"),
        headers=payload.get("headers"),
        classification=classification,
        classifier="auto",
        matched_campaign_id=None,  # TODO(二期)：按 Message-ID/token 精确匹配演练
    )
    if classification == "drill" and reporter_user_id:
        report.reward_points = 10
    db.add(report)
    db.flush()
    if classification == "drill" and reporter_user_id:
        db.add(ReportRewardLog(user_id=reporter_user_id, report_id=report.id,
                               points=10, reason="演练邮件举报"))
    db.commit()
    db.refresh(report)
    return report.id
