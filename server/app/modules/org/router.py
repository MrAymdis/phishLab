from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.core.pagination import page_params
from app.db.session import get_db

from . import service

depts = APIRouter(prefix="/api/v1/depts", tags=["用户和组"], dependencies=[Depends(get_current_account)])
emp_users = APIRouter(prefix="/api/v1/emp-users", tags=["用户和组"], dependencies=[Depends(get_current_account)])
groups = APIRouter(prefix="/api/v1/groups", tags=["用户和组"], dependencies=[Depends(get_current_account)])
tags = APIRouter(prefix="/api/v1/tags", tags=["用户和组"], dependencies=[Depends(get_current_account)])
routers = [depts, emp_users, groups, tags]


class DeptCreate(BaseModel):
    parent_id: int = 0
    name: str
    code: str | None = None


class EmpUserCreate(BaseModel):
    emp_no: str | None = None
    name: str
    email: EmailStr
    mobile: str | None = None  # 服务端加密后存储
    dept_id: int
    position: str | None = None
    tag_ids: list[int] = []
    initial_risk: int = 50


@depts.get("", summary="部门树（含人数）")
def tree(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.dept_tree(db, account))


@depts.post("", summary="添加部门")
def create(payload: DeptCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_dept(db, account, payload.model_dump())})


@depts.post("/sync", summary="触发组织架构同步（LDAP/企微/钉钉/飞书）")
def sync(source: str = Query(..., description="ldap/wecom/dingtalk/feishu"),
         account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.sync_org(db, account, source))


@emp_users.get("", summary="员工档案列表（标签/风险筛选）")
def list_users(
    dept_id: int | None = None,
    tag: str | None = None,
    risk_level: int | None = Query(None, description="1低 2中 3高"),
    kw: str | None = None,
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.list_users(db, account, dept_id=dept_id, tag=tag, risk_level=risk_level, kw=kw, page=page, page_size=page_size))


@emp_users.post("/import", summary="CSV 批量导入员工（工号,姓名,邮箱[,部门,岗位,手机号,初始风险]）")
async def import_csv(file: UploadFile = File(...), account=Depends(get_current_account), db: Session = Depends(get_db)):
    content = await file.read()
    return resp.ok(service.import_users_csv(db, account, content))


@emp_users.post("", summary="添加员工")
def create_user(payload: EmpUserCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_user(db, account, payload.model_dump())})


@emp_users.get("/{uid}", summary="员工档案详情（含历史轨迹）")
def user_detail(uid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_user(db, account, uid))


@emp_users.put("/{uid}", summary="编辑员工")
def update_user(uid: int, payload: EmpUserCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_user(db, account, uid, payload.model_dump()))


@emp_users.delete("/{uid}", summary="删除员工（离职软删）")
def delete_user(uid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_user(db, account, uid))


@emp_users.get("/{uid}/risk-profile", summary="员工风险画像（五维）")
def risk_profile(uid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_risk_profile(db, account, uid))


@groups.get("", summary="分组列表")
def list_groups(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_groups(db, account))


class TagCreate(BaseModel):
    name: str
    color: str | None = None


@tags.get("", summary="标签列表")
def list_tags(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_tags(db, account))


@tags.post("", summary="创建标签（名称唯一）")
def create_tag(payload: TagCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_tag(db, account, payload.model_dump())})
