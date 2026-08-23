"""Celery 应用：投递引擎与定时任务。

启动：celery -A worker worker / celery -A worker beat（beat 单实例）
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "phishlab",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.delivery",
        "worker.tasks.track_stream",
        "worker.tasks.stat_aggregate",
        "worker.tasks.retention_clean",
        "worker.tasks.risk_recalc",
        "worker.tasks.campaign_auto",
        "worker.tasks.bounce_scanner",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_acks_late=True,          # 发送任务失败可重投
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    # 每 30s 扫描到期演练批次并派发投递任务
    "dispatch-due-batches": {
        "task": "worker.tasks.delivery.dispatch_due_batches",
        "schedule": 30.0,
    },
    # 每 10s 消费追踪事件流（打开/点击/提交 → track_event + 计数 + 预警）
    "track-consume": {
        "task": "worker.tasks.track_stream.consume",
        "schedule": 10.0,
    },
    # 注：DNS 巡检已改为手动触发（API: GET /api/v1/domains/{id}/dns-check，发送配置页
    # 域名列表「检测」按钮）——自动巡检的 dnspython 同步查询会阻塞投递 worker 线程，
    # 且域名 DNS 记录配置后极少变化，定时巡检价值有限。
    # 每分钟扫描到点的定时演练并自动启动（scheduled + schedule_at <= now）
    "campaign-auto-start": {
        "task": "worker.tasks.campaign_auto.start_scheduled",
        "schedule": 60.0,
    },
    # 每 5 分钟扫描 running 演练：投递完毕/到期自动置 completed
    "campaign-auto-complete": {
        "task": "worker.tasks.campaign_auto.auto_complete",
        "schedule": crontab(minute="*/5"),
    },
    # 每 10 分钟补齐 stat_daily 日聚合（幂等：缺天才写，首次自动回填近 90 天）
    "stat-aggregate": {
        "task": "worker.tasks.stat_aggregate.aggregate",
        "schedule": crontab(minute="*/10"),
    },
    # 每日 02:00 重算员工风险画像
    "risk-recalc": {
        "task": "worker.tasks.risk_recalc.recalc",
        "schedule": crontab(hour=2, minute=0),
    },
    # 每日 03:00 数据留存清理（platform_setting.retention_days）
    "retention-clean": {
        "task": "worker.tasks.retention_clean.clean",
        "schedule": crontab(hour=3, minute=0),
    },
    # 每 5 分钟回扫各 SMTP 通道收件箱：退信 → 目标 sent→bounced + 原因
    # （QQ 退信通常在投递后几分钟内到达，5 分钟间隔保证"退信到、状态即改"）
    "scan-bounces": {
        "task": "worker.tasks.bounce_scanner.scan_bounces",
        "schedule": crontab(minute="*/5"),
    },
}
