"""一次性修复：清理已删除演练残留的孤儿 track_event / campaign_batch，并重算受影响员工画像。

背景：删除演练级联清除 TrackEvent 的修复（commit 75fb086）之前删除的演练，
track_event 已级联删掉但事件表残留——emp_risk_profile.phish_count 快照与
"历史中招"轨迹因此出现"活动已删、档案仍有中招数据"。本脚本清掉这些孤儿行，
并按与 worker risk_recalc 同口径重算受影响员工的画像。

用法（默认 dry-run，只打印将发生的变化）：
    python scripts/repair_orphan_track_events.py
    python scripts/repair_orphan_track_events.py --apply
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.campaign.models import Campaign, CampaignBatch  # noqa: E402
from app.modules.org.models import EmpRiskProfile  # noqa: E402
from app.modules.tracking.models import TrackEvent  # noqa: E402

_PHISH_TYPES = ("submit", "attach_run")


def _event_snapshot(db):
    """孤儿/存活事件汇总：(total, orphan_n, orphan_by_type, per_user)。"""
    c = Campaign.__table__
    # 左连接后孤儿行的 campaign_id 被 SQL 置 NULL（e.campaign_id 有值但无匹配），
    # 不能再按 TrackEvent.campaign_id 过滤——会恰好滤掉全部孤儿行。
    rows = db.execute(
        select(
            TrackEvent.user_id, c.c.id, TrackEvent.event_type,
            func.count(TrackEvent.id),
        )
        .join(c, c.c.id == TrackEvent.campaign_id, isouter=True)
        .group_by(TrackEvent.user_id, c.c.id, TrackEvent.event_type)
    ).all()
    per_user: dict[int, dict[str, dict[str, int]]] = {}
    by_type: dict[str, int] = {}
    orphan = 0
    for uid, c_id, etype, n in rows:
        live = c_id is not None  # 无匹配 campaign 行 ⇒ 孤儿
        if not live:
            orphan += n
            by_type[etype] = by_type.get(etype, 0) + n
        if uid is not None:
            key = "live" if live else "orphan"
            bucket = per_user.setdefault(int(uid), {"live": {}, "orphan": {}})[key]
            bucket[etype] = bucket.get(etype, 0) + int(n)
    return rows, orphan, by_type, per_user


def main() -> None:
    ap = argparse.ArgumentParser(description="清理删除演练残留的孤儿追踪事件")
    ap.add_argument("--apply", action="store_true", help="实际落库；缺省 dry-run")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows, orphan, by_type, per_user = _event_snapshot(db)
        orphan_batches = list(db.execute(
            select(CampaignBatch.id)
            .join(Campaign, Campaign.id == CampaignBatch.campaign_id, isouter=True)
            .where(Campaign.id.is_(None))
        ).scalars())

        if not orphan and not orphan_batches:
            print("无孤儿数据，无需修复。")
            return

        mode = "APPLY" if args.apply else "DRY-RUN（未落库，加 --apply 执行）"
        print(f"[{mode}] 孤儿 track_event：{orphan} 行（总数 {sum(n for _, _, _, n in rows)}）")
        print(f"  按类型：{dict(sorted(by_type.items()))}")
        if orphan_batches:
            print(f"  孤儿 campaign_batch：{len(orphan_batches)} 行（id={orphan_batches}）")

        affected = [uid for uid, b in per_user.items() if b["orphan"]]
        if not affected:
            print("无受画像影响员工。")
            return
        print(f"\n受影响员工画像（phish_count 口径=submit+attach_run）：")
        profiles = db.execute(
            select(EmpRiskProfile.user_id, EmpRiskProfile.phish_count)
            .where(EmpRiskProfile.user_id.in_(affected))
        ).all()
        current = {int(uid): int(n or 0) for uid, n in profiles}
        for uid in sorted(affected):
            b = per_user[uid]
            orph_phish = sum(b["orphan"].get(t, 0) for t in _PHISH_TYPES)
            live_phish = sum(b["live"].get(t, 0) for t in _PHISH_TYPES)
            print(f"  user {uid}: 快照 {current.get(uid, 0)} → 重算后 ~{live_phish}"
                  f"（删除孤儿中招 {orph_phish} 行；孤儿明细 "
                  f"{b['orphan']}；存活明细 {b['live']}）")

        if not args.apply:
            return

        orphan_ids = [
            r[0] for r in db.execute(
                select(TrackEvent.id)
                .join(Campaign, Campaign.id == TrackEvent.campaign_id, isouter=True)
                .where(Campaign.id.is_(None))
            ).all()
        ]
        deleted = db.execute(
            TrackEvent.__table__.delete().where(TrackEvent.id.in_(orphan_ids))
        ).rowcount
        db.execute(
            CampaignBatch.__table__.delete().where(CampaignBatch.id.in_(orphan_batches))
        )
        db.commit()
        print(f"\n已删除孤儿 track_event {deleted} 行、campaign_batch {len(orphan_batches)} 行。")

        from worker.tasks.risk_recalc import recalc
        for uid in affected:
            n = recalc(uid)
            print(f"  user {uid} 画像重算完成（共处理 {n} 人）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
