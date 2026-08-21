"""统计汇总任务：track_event / campaign_target → stat_daily 日维度归档。

stat_daily 是留存清理（retention_clean，到期删除/匿名化 track_event）后唯一保留的
长期趋势数据：平台 / 部门 / 场景 / 用户四维度每日聚合，供趋势报表与个人画像读取；
实时报表仍直查事实表（campaign_target），本表为归档与历史回放。

注：架构设计的 Redis cnt:{campaignId} 实时计数层未启用——当前由
track_stream 消费者单写 campaign_stat（无竞争），规模上来再迁 Redis。
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import case, distinct, func, select

from app.db.session import SessionLocal
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.stat")

_BACKFILL_DAYS = 90  # 每次运行补齐最近 N 天缺失的日聚合（缺行=零值语义）
_SENT_STATUS = ("sent", "delivered", "bounced", "failed")
_EVENT_TYPES = ("open", "click", "submit", "report")


def _aggregate_day(db, day: date) -> int:
    """聚合单日 stat_daily 四维度，返回写入行数（全零天不落行）。"""
    from app.modules.analytics.models import StatDaily
    from app.modules.campaign.models import Campaign, CampaignTarget
    from app.modules.org.models import EmpUser
    from app.modules.tracking.models import TrackEvent

    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    rows: list[StatDaily] = []

    def add(dim_type: str, dim_id=None, dim_key=None, **cnts):
        if any(cnts.values()):
            rows.append(StatDaily(
                stat_date=day, dim_type=dim_type, dim_id=dim_id, dim_key=dim_key,
                **cnts,
            ))

    def events_cnt(event_type: str, **where):
        return int(db.scalar(
            select(func.count(distinct(TrackEvent.user_id))).where(
                TrackEvent.event_type == event_type,
                TrackEvent.created_at >= day_start,
                TrackEvent.created_at < day_end,
                *where,
            )
        ) or 0)

    target_sent = CampaignTarget.send_status.in_(_SENT_STATUS)
    delivered_case = case((CampaignTarget.send_status.in_(("sent", "delivered")), 1), else_=0)

    # ---- 平台维度 ----
    add("platform",
        campaign_cnt=int(db.scalar(
            select(func.count()).select_from(Campaign)
            .where(Campaign.created_at >= day_start, Campaign.created_at < day_end)
        ) or 0),
        target_cnt=int(db.scalar(
            select(func.count()).select_from(CampaignTarget)
            .where(target_sent, CampaignTarget.sent_at >= day_start, CampaignTarget.sent_at < day_end)
        ) or 0),
        delivered_cnt=int(db.scalar(
            select(func.coalesce(func.sum(delivered_case), 0)).select_from(CampaignTarget)
            .where(CampaignTarget.sent_at >= day_start, CampaignTarget.sent_at < day_end)
        ) or 0),
        open_cnt=events_cnt("open"),
        click_cnt=events_cnt("click"),
        submit_cnt=events_cnt("submit"),
        report_cnt=events_cnt("report"),
    )

    # ---- 部门维度（按事件/投递归属员工当前部门） ----
    tgt_by_dept = {
        int(dept_id): (n, d)
        for dept_id, n, d in db.execute(
            select(EmpUser.dept_id,
                   func.count(CampaignTarget.id),
                   func.coalesce(func.sum(delivered_case), 0))
            .join(CampaignTarget, CampaignTarget.user_id == EmpUser.id)
            .where(EmpUser.dept_id.is_not(None),
                   CampaignTarget.sent_at >= day_start, CampaignTarget.sent_at < day_end)
            .group_by(EmpUser.dept_id)
        ).all()
    }
    evt_by_dept: dict[int, dict[str, int]] = {}
    for dept_id, etype, n in db.execute(
        select(EmpUser.dept_id, TrackEvent.event_type, func.count(distinct(TrackEvent.user_id)))
        .join(EmpUser, EmpUser.id == TrackEvent.user_id)
        .where(EmpUser.dept_id.is_not(None),
               TrackEvent.created_at >= day_start, TrackEvent.created_at < day_end)
        .group_by(EmpUser.dept_id, TrackEvent.event_type)
    ).all():
        evt_by_dept.setdefault(int(dept_id), {})[etype] = int(n or 0)
    for dept_id in set(tgt_by_dept) | set(evt_by_dept):
        ev = evt_by_dept.get(dept_id, {})
        target_cnt, delivered = tgt_by_dept.get(dept_id, (0, 0))
        add("dept", dim_id=dept_id,
            target_cnt=int(target_cnt or 0), delivered_cnt=int(delivered or 0),
            open_cnt=int(ev.get("open", 0)), click_cnt=int(ev.get("click", 0)),
            submit_cnt=int(ev.get("submit", 0)), report_cnt=int(ev.get("report", 0)),
        )

    # ---- 场景维度（演练方式） ----
    camp_by_type = {
        ctype: n for ctype, n in db.execute(
            select(Campaign.type, func.count())
            .where(Campaign.created_at >= day_start, Campaign.created_at < day_end,
                   Campaign.type.is_not(None))
            .group_by(Campaign.type)
        ).all()
    }
    tgt_by_type = {
        ctype: (n, d) for ctype, n, d in db.execute(
            select(Campaign.type,
                   func.count(CampaignTarget.id),
                   func.coalesce(func.sum(delivered_case), 0))
            .join(CampaignTarget, CampaignTarget.campaign_id == Campaign.id)
            .where(Campaign.type.is_not(None),
                   CampaignTarget.sent_at >= day_start, CampaignTarget.sent_at < day_end)
            .group_by(Campaign.type)
        ).all()
    }
    evt_by_type: dict[str, dict[str, int]] = {}
    for ctype, etype, n in db.execute(
        select(Campaign.type, TrackEvent.event_type, func.count(distinct(TrackEvent.user_id)))
        .join(TrackEvent, TrackEvent.campaign_id == Campaign.id)
        .where(Campaign.type.is_not(None),
               TrackEvent.created_at >= day_start, TrackEvent.created_at < day_end)
        .group_by(Campaign.type, TrackEvent.event_type)
    ).all():
        evt_by_type.setdefault(ctype, {})[etype] = int(n or 0)
    for ctype in set(camp_by_type) | set(tgt_by_type) | set(evt_by_type):
        ev = evt_by_type.get(ctype, {})
        target_cnt, delivered = tgt_by_type.get(ctype, (0, 0))
        add("scene", dim_key=ctype,
            campaign_cnt=int(camp_by_type.get(ctype, 0) or 0),
            target_cnt=int(target_cnt or 0), delivered_cnt=int(delivered or 0),
            open_cnt=int(ev.get("open", 0)), click_cnt=int(ev.get("click", 0)),
            submit_cnt=int(ev.get("submit", 0)), report_cnt=int(ev.get("report", 0)),
        )

    # ---- 用户维度（个人日行为序列，供个人画像趋势） ----
    tgt_by_user = {
        int(uid): (n, d) for uid, n, d in db.execute(
            select(CampaignTarget.user_id,
                   func.count(CampaignTarget.id),
                   func.coalesce(func.sum(delivered_case), 0))
            .where(CampaignTarget.sent_at >= day_start, CampaignTarget.sent_at < day_end)
            .group_by(CampaignTarget.user_id)
        ).all()
    }
    evt_by_user: dict[int, dict[str, int]] = {}
    for uid, etype, n in db.execute(
        select(TrackEvent.user_id, TrackEvent.event_type, func.count(distinct(TrackEvent.user_id)))
        .where(TrackEvent.created_at >= day_start, TrackEvent.created_at < day_end)
        .group_by(TrackEvent.user_id, TrackEvent.event_type)
    ).all():
        evt_by_user.setdefault(int(uid), {})[etype] = int(n or 0)
    for uid in set(tgt_by_user) | set(evt_by_user):
        ev = evt_by_user.get(uid, {})
        target_cnt, delivered = tgt_by_user.get(uid, (0, 0))
        add("user", dim_id=uid,
            target_cnt=int(target_cnt or 0), delivered_cnt=int(delivered or 0),
            open_cnt=int(ev.get("open", 0)), click_cnt=int(ev.get("click", 0)),
            submit_cnt=int(ev.get("submit", 0)), report_cnt=int(ev.get("report", 0)),
        )

    db.add_all(rows)
    return len(rows)


@celery_app.task(name="worker.tasks.stat_aggregate.aggregate")
def aggregate():
    """stat_daily 日聚合（幂等）：补齐最近 _BACKFILL_DAYS 天缺失的日归档。

    仅聚合已结束的整天（不含今天，避免每轮重写当日部分数据）；
    首次运行自动回填近 90 天历史（track_event 事实表在库即可重建）；
    已聚合的天跳过，beat 高频调用时为空检查。
    """
    from app.modules.analytics.models import StatDaily

    db = SessionLocal()
    try:
        today = date.today()
        since = today - timedelta(days=_BACKFILL_DAYS)
        existing = set(db.scalars(
            select(StatDaily.stat_date)
            .where(StatDaily.stat_date >= since, StatDaily.stat_date < today)
            .distinct()
        ).all())
        written_days = written_rows = 0
        for i in range(_BACKFILL_DAYS, 0, -1):
            day = today - timedelta(days=i)
            if day in existing:
                continue
            written_days += 1
            written_rows += _aggregate_day(db, day)
        db.commit()
        if written_rows:
            logger.info("stat_daily 聚合：补 %s 天共 %s 行", written_days, written_rows)
        return written_rows
    except Exception:
        db.rollback()
        logger.exception("stat_daily 聚合失败")
        raise
    finally:
        db.close()
        _check_stream_lag()


def _check_stream_lag():
    """evt:stream 滞留检查：pending 超过阈值时告警日志（消费异常兜底）。"""
    import redis

    from app.core.config import settings
    from app.modules.tracking.stream import EVENT_GROUP, EVENT_STREAM

    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        info = r.xpending(EVENT_STREAM, EVENT_GROUP)
        pending = info.get("pending") if isinstance(info, dict) else info[0]
        if int(pending or 0) > 2000:
            logger.warning("evt:stream 滞留 %s 条待消费，请检查 track-consume 消费者", pending)
    except Exception:
        pass  # Redis 不可用 / 消费组未创建时静默
