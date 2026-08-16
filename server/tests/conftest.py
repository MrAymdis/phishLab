"""测试夹具：在导入应用前将 DATABASE_URL 指向临时 SQLite，建表并种子化测试账号。"""
import os
import tempfile

_tmp = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}"

import pytest  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.modules.account.models import SysAccount  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(SysAccount(id=1, username="tester", password_hash=hash_password("x"), real_name="测试员", status=1))
    db.commit()
    db.close()
    yield
