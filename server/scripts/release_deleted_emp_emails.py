"""存量软删员工邮箱释放：status=0 且 email 未带 #del 后缀的行，加后缀释放唯一索引。

背景：修复前的 delete_user 软删只置 status=0，email 唯一索引仍被占用，
重新添加同邮箱员工会撞 uk 约束 500（修复后的新删除不再产生此类行）。
用法：.venv/bin/python scripts/release_deleted_emp_emails.py [--apply]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.org.models import EmpUser  # noqa: E402

_RELEASED = re.compile(r"#del\d+$")


def main() -> None:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    try:
        rows = db.scalars(select(EmpUser).where(EmpUser.status == 0)).all()
        stale = [u for u in rows if not _RELEASED.search(u.email or "")]
        print(f"status=0 共 {len(rows)} 行，需释放邮箱 {len(stale)} 行" + ("" if apply else "（dry-run）"))
        for u in stale:
            new_email = f"{(u.email or '')[:100]}#del{u.id}"
            print(f"  id={u.id:<5} {u.email} → {new_email}")
            if apply:
                u.email = new_email
        if apply:
            db.commit()
            print("✓ 已应用")
    finally:
        db.close()


if __name__ == "__main__":
    main()
