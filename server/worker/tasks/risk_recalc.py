"""员工风险画像重算任务：按初始风险 + 历史行为事件全量重算五维与综合分。

口径与实时消费（track_stream）一致：
- 初始五维 = initial_risk（五维仅作展示）
- 行为增量：open→邮件识别+3 / click→链接点击+8 / submit→密码提交+15、中招+1
  / report→举报意识+10、举报+1
- 综合分 = 初始风险 + 打开×2 + 点击×3 + 提交×10 − 举报×15，
  等级 0-70 低 / 71-80 中 / 81-100 高
"""
import logging

from sqlalchemy import func, select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.risk")


@celery_app.task(name="worker.tasks.risk_recalc.recalc")
def recalc(user_id: int | None = None) -> int:
    """全量（或指定员工）重算 emp_risk_profile；返回重算人数。"""
    from app.db.session import SessionLocal
    from app.modules.org.models import EmpRiskProfile, EmpUser
    from app.modules.org.service import (
        _DIM_OFFSETS, _behavior_counts, _risk_level_of, _total_from_behavior,
    )
    from app.modules.tracking.models import TrackEvent

    db = SessionLocal()
    try:
        stmt = select(EmpUser).where(EmpUser.status == 1)
        if user_id:
            stmt = stmt.where(EmpUser.id == user_id)
        users = db.scalars(stmt).all()

        for u in users:
            base = min(max(u.initial_risk or 70, 0), 100)
            dims = [min(max(base + off, 0), 100) for off in _DIM_OFFSETS]
            phish = 0
            report = 0

            rows = db.execute(
                select(TrackEvent.event_type, func.count(TrackEvent.id))
                .where(TrackEvent.user_id == u.id)
                .group_by(TrackEvent.event_type)
            ).all()
            for event_type, cnt in rows:
                n = int(cnt)
                if event_type == "submit":
                    phish += n
                    dims[2] = min(100, dims[2] + 15 * n)
                elif event_type == "click":
                    dims[1] = min(100, dims[1] + 8 * n)
                elif event_type == "open":
                    dims[0] = min(100, dims[0] + 3 * n)
                elif event_type == "report":
                    report += n
                    dims[4] = min(100, dims[4] + 10 * n)
                elif event_type == "attach_run":
                    phish += n  # 中招次数口径与提交合并（附件运行=中招），与 track_stream 实时消费一致
                    dims[3] = min(100, dims[3] + 10 * n)

            # 综合评分：行为次数直接计分（五维仅作展示）
            counts = _behavior_counts(db, u.id)
            total = _total_from_behavior(
                base, counts["open_n"], counts["click_n"],
                counts["submit_n"], counts["report_n"], counts["attach_n"],
            )
            profile = db.get(EmpRiskProfile, u.id)
            if profile is None:
                profile = EmpRiskProfile(user_id=u.id)
                db.add(profile)
            profile.email_recognize, profile.link_click = dims[0], dims[1]
            profile.pwd_submit, profile.attach_run = dims[2], dims[3]
            profile.report_awareness = dims[4]
            profile.phish_count = phish
            profile.report_count = report
            profile.total_score = total
            profile.risk_level = _risk_level_of(total)

        db.commit()
        logger.info("risk recalc done: %d users", len(users))
        return len(users)
    finally:
        db.close()
