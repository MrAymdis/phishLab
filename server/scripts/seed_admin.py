"""初始化超级管理员账号（幂等）：admin / PhishLab@2026。

用法：python scripts/seed_admin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.account.models import SysAccount  # noqa: E402

USERNAME = "admin"
PASSWORD = "PhishLab@2026"


def main():
    db = SessionLocal()
    try:
        exists = db.query(SysAccount).filter_by(username=USERNAME).first()
        if exists:
            print(f"账号 {USERNAME} 已存在，跳过。")
            return
        db.add(SysAccount(
            username=USERNAME,
            password_hash=hash_password(PASSWORD),
            real_name="超级管理员",
            status=1,
        ))
        db.commit()
        print(f"已创建超管账号：{USERNAME} / {PASSWORD}（请尽快修改密码）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
