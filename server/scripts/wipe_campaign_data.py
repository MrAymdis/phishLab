"""清空演练+追踪域全部数据（不可回滚，默认 dry-run）。

范围（用户确认：演练+追踪域全清）：
- 演练域：campaign / campaign_target / campaign_batch / campaign_stat / campaign_alert
- 追踪域：track_event / fingerprint / stat_daily（趋势归档）
- 员工画像行为部分归零：emp_risk_profile 按 initial_risk 重置为基线
  （与 worker risk_recalc 同口径：无行为时 dims=initial_risk、总分=initial_risk、
  phish_count/report_count=0、等级按 _risk_level_of）

保留：组织（emp_user/emp_dept/组/标签）、素材（模板/落地页/二维码）、
培训、举报、AI 草稿、通道配置、账号/RBAC、审计日志。

用法：
    python scripts/wipe_campaign_data.py            # dry-run
    python scripts/wipe_campaign_data.py --apply    # 落库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.analytics.models import StatDaily  # noqa: E402
from app.modules.campaign.models import (  # noqa: E402
    Campaign, CampaignAlert, CampaignBatch, CampaignStat, CampaignTarget,
)
from app.modules.org.models import EmpRiskProfile, EmpUser  # noqa: E402
from app.modules.org.service import _DIM_OFFSETS, _risk_level_of  # noqa: E402
from app.modules.tracking.models import Fingerprint, TrackEvent  # noqa: E402

# 先子后父（库无外键约束，顺序仅为可读性）
WIPE_TABLES = [
    ("track_event", TrackEvent),
    ("campaign_alert", CampaignAlert),
    ("campaign_batch", CampaignBatch),
    ("campaign_stat", CampaignStat),
    ("campaign_target", CampaignTarget),
    ("fingerprint", Fingerprint),
    ("stat_daily", StatDaily),
    ("campaign", Campaign),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="清空演练+追踪域数据")
    ap.add_argument("--apply", action="store_true", help="实际落库；缺省 dry-run")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        mode = "APPLY" if args.apply else "DRY-RUN（未落库，加 --apply 执行）"
        print(f"[{mode}]")

        # ---- 将删表行数 ----
        print("\n各表将清空：")
        table_counts: dict[str, int] = {}
        for name, model in WIPE_TABLES:
            n = int(db.scalar(select(func.count()).select_from(model)) or 0)
            table_counts[name] = n
            print(f"  {name}: {n} 行")
        total = sum(table_counts.values())

        # ---- 画像归零预览 ----
        print("\n员工画像行为归零（基线=initial_risk，口径同 risk_recalc）：")
        profile_changes: list[dict] = []
        for u, p in db.execute(
            select(EmpUser, EmpRiskProfile)
            .join(EmpRiskProfile, EmpRiskProfile.user_id == EmpUser.id)
        ).all():
            base = min(max(int(u.initial_risk or 70), 0), 100)
            # _DIM_OFFSETS 全零 ⇒ 五维=初始风险=总分
            after = {
                "phish": 0, "report": 0,
                "total": base, "risk": _risk_level_of(base),
            }
            before = {
                "phish": int(p.phish_count or 0), "report": int(p.report_count or 0),
                "total": int(p.total_score or 0), "risk": int(p.risk_level or 0),
            }
            changed = before != after
            profile_changes.append({"user": u, "before": before, "after": after, "changed": changed})
            if changed:
                print(f"  {u.name} (uid={u.id}, 初始风险 {base}): "
                      f"phish {before['phish']}→0, 总分 {before['total']}→{after['total']}, "
                      f"等级 {before['risk']}→{after['risk']}")
            else:
                print(f"  {u.name} (uid={u.id}): 已为基线，无变化")
        n_changed = sum(1 for c in profile_changes if c["changed"])

        print(f"\n小计：清 {total} 行（{len(table_counts)} 表），画像重置 {n_changed}/{len(profile_changes)} 人")
        print("保留：组织/素材/培训/举报/AI 草稿/通道/账号/审计日志")

        if not args.apply:
            return

        # ---- 落库 ----
        for name, model in WIPE_TABLES:
            n = db.execute(delete(model)).rowcount
            print(f"  已清空 {name}: {n} 行")
        for c in profile_changes:
            if not c["changed"]:
                continue
            p = db.get(EmpRiskProfile, c["user"].id)
            base = c["after"]["total"]
            p.email_recognize = p.link_click = p.pwd_submit = p.attach_run = p.report_awareness = base
            p.phish_count = 0
            p.report_count = 0
            p.total_score = base
            p.risk_level = c["after"]["risk"]
        db.commit()
        print(f"\n完成：演练+追踪域已清空，{n_changed} 名员工画像归零。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
