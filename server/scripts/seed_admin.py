"""初始化超级管理员账号（幂等）：admin / PhishLab@2026。

与 POST /api/v1/auth/init 共用 bootstrap_super_admin（同时补建 super_admin
角色并绑定——只建账号不建角色会导致所有端点 403）。

用法：python scripts/seed_admin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.errors import BizError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.account.models import SysAccount  # noqa: E402
from app.modules.account.service import bootstrap_super_admin  # noqa: E402
from sqlalchemy import select  # noqa: E402

USERNAME = "admin"
PASSWORD = "PhishLab@2026"


def main():
    db = SessionLocal()
    try:
        exists = db.scalar(select(SysAccount.id).where(SysAccount.username == USERNAME).limit(1))
        if exists:
            print(f"账号 {USERNAME} 已存在，跳过。")
            return
        try:
            bootstrap_super_admin(db, USERNAME, PASSWORD, real_name="超级管理员")
        except BizError as e:
            print(f"初始化失败：{e.message}")
            sys.exit(1)
        print(f"已创建超管账号：{USERNAME} / {PASSWORD}（请尽快修改密码）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
