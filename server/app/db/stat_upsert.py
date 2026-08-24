"""CampaignStat 跨库原子累加（insert-or-increment）。

生产 MySQL 用 INSERT ... ON DUPLICATE KEY UPDATE 原子累加（并发消费防 lost update）；
SQLite（测试 / 轻量单机部署）回退为 select-or-create + 原地变更，语义一致。
"""
from sqlalchemy import func

from app.db.session import engine


def stat_inc(db, campaign_id: int, **deltas: int) -> None:
    """按 campaign_id 对 CampaignStat 列做 ±delta 累加（结果不小于 0）。

    例：stat_inc(db, 1, delivered_cnt=1)；stat_inc(db, 1, delivered_cnt=-1)。
    """
    from app.modules.campaign.models import CampaignStat

    if engine.dialect.name == "mysql":
        from sqlalchemy.dialects.mysql import insert

        stmt = insert(CampaignStat).values(
            campaign_id=campaign_id, **{k: max(v, 0) for k, v in deltas.items()}
        )
        db.execute(stmt.on_duplicate_key_update(**{
            col: func.greatest(getattr(CampaignStat, col) + delta, 0)
            for col, delta in deltas.items()
        }))
        return

    stat = db.get(CampaignStat, campaign_id)
    if stat is None:
        db.add(CampaignStat(
            campaign_id=campaign_id, **{k: max(v, 0) for k, v in deltas.items()}))
        return
    for col, delta in deltas.items():
        setattr(stat, col, max(getattr(stat, col) + delta, 0))
