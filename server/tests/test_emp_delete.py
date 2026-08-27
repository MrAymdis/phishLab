"""员工删除（离职软删）邮箱释放：重加同邮箱不再撞唯一约束；原始邮箱留审计。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.org.service import create_user, delete_user
from app.modules.rbac.models import AuditLog

EMAIL = "anfu@xmkmsec.cn"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (AuditLog, EmpRiskProfile, EmpUser, EmpDept):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _account(db) -> SysAccount:
    return db.get(SysAccount, 1)


def _new_emp(db, name: str = "测试员工", email: str = EMAIL) -> EmpUser:
    dept = EmpDept(name="测试部", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    emp_id = create_user(db, _account(db), {"name": name, "email": email, "dept_id": dept.id})
    return db.get(EmpUser, emp_id)


def test_delete_releases_email_and_readd_succeeds():
    db = SessionLocal()
    emp = _new_emp(db)
    delete_user(db, _account(db), emp.id)

    row = db.get(EmpUser, emp.id)
    assert row.status == 0
    assert row.email == f"{EMAIL}#del{emp.id}"  # 释放唯一索引

    # 重加同邮箱：修复前撞 uk_emp_user_email → 500
    new_id = create_user(db, _account(db), {"name": "重新入职", "email": EMAIL, "dept_id": row.dept_id})
    assert new_id != emp.id
    db.close()


def test_delete_audit_keeps_original_email():
    db = SessionLocal()
    emp = _new_emp(db)
    delete_user(db, _account(db), emp.id)

    audit = db.scalar(select(AuditLog).where(
        AuditLog.action == "delete_user", AuditLog.target_id == str(emp.id)))
    assert audit is not None
    assert audit.detail["email"] == EMAIL  # 审计保留原始邮箱，非 #del 后缀值
    db.close()
