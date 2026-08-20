from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service

courses = APIRouter(prefix="/api/v1/courses", tags=["安全培训"], dependencies=[Depends(get_current_account)])
tasks = APIRouter(prefix="/api/v1/training-tasks", tags=["安全培训"], dependencies=[Depends(get_current_account)])
exam = APIRouter(prefix="/api/v1/exam", tags=["安全培训"], dependencies=[Depends(get_current_account)])
routers = [courses, tasks, exam]


@courses.get("", summary="课程库列表")
def list_courses(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_courses(db, account))


@courses.post("", summary="新建课程", dependencies=[Depends(require_perm("training:manage"))])
def create_course(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_course(db, account, payload)})


@tasks.get("", summary="培训任务列表")
def list_tasks(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_tasks(db, account))


@tasks.post("", summary="创建培训任务（人群快照 + 期限）", dependencies=[Depends(require_perm("training:manage"))])
def create_task(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_task(db, account, payload)})


@exam.get("/questions", summary="题库列表")
def list_questions(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_questions(db, account))


@exam.get("/papers", summary="试卷列表")
def list_papers(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_papers(db, account))
