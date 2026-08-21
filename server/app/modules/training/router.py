from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.core.pagination import page_params
from app.db.session import get_db

from . import service

courses = APIRouter(prefix="/api/v1/courses", tags=["安全培训"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/training"))])
tasks = APIRouter(prefix="/api/v1/training-tasks", tags=["安全培训"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/training"))])
exam = APIRouter(prefix="/api/v1/exam", tags=["安全培训"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/training"))])
routers = [courses, tasks, exam]


# ---------- 课程库 ----------

@courses.get("", summary="课程库列表")
def list_courses(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_courses(db, account))


@courses.get("/{cid}", summary="课程详情（预览）")
def get_course(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_course(db, account, cid))


@courses.post("", summary="新建课程", dependencies=[Depends(require_perm("training:manage"))])
def create_course(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_course(db, account, payload)})


@courses.put("/{cid}", summary="编辑课程", dependencies=[Depends(require_perm("training:manage"))])
def update_course(cid: int, payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_course(db, account, cid, payload))


@courses.delete("/{cid}", summary="删除课程（被引用时阻止）", dependencies=[Depends(require_perm("training:manage"))])
def delete_course(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_course(db, account, cid))


# ---------- 培训任务 ----------

@tasks.get("", summary="培训任务列表")
def list_tasks(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_tasks(db, account))


@tasks.get("/{tid}", summary="任务详情（人员学习明细）")
def get_task(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_task(db, account, tid))


@tasks.post("", summary="创建培训任务（人群快照 + 期限）", dependencies=[Depends(require_perm("training:manage"))])
def create_task(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_task(db, account, payload)})


@tasks.post("/{tid}/close", summary="关闭培训任务", dependencies=[Depends(require_perm("training:manage"))])
def close_task(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.close_task(db, account, tid))


@tasks.post("/{tid}/remind", summary="催办（统计未完成 + 审计）", dependencies=[Depends(require_perm("training:manage"))])
def remind_task(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.remind_task(db, account, tid))


@tasks.delete("/{tid}", summary="删除培训任务", dependencies=[Depends(require_perm("training:manage"))])
def delete_task(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_task(db, account, tid))


@tasks.get("/{tid}/export", summary="导出任务人员明细 Excel", dependencies=[Depends(require_perm("training:manage"))])
def export_task(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    content, filename = service.export_task_xlsx(db, account, tid)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ---------- 题库 ----------

@exam.get("/questions", summary="题库列表")
def list_questions(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_questions(db, account))


@exam.get("/questions/{qid}", summary="题目详情（含答案，管理端回填）")
def get_question(qid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_question(db, account, qid))


@exam.post("/questions", summary="新建题目", dependencies=[Depends(require_perm("training:manage"))])
def create_question(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_question(db, account, payload)})


@exam.put("/questions/{qid}", summary="编辑题目", dependencies=[Depends(require_perm("training:manage"))])
def update_question(qid: int, payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_question(db, account, qid, payload))


@exam.delete("/questions/{qid}", summary="删除题目（被试卷引用时阻止）", dependencies=[Depends(require_perm("training:manage"))])
def delete_question(qid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_question(db, account, qid))


# ---------- 试卷 ----------

@exam.get("/papers", summary="试卷列表")
def list_papers(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_papers(db, account))


@exam.get("/papers/{pid}", summary="试卷详情（预览，含答案）")
def get_paper(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_paper(db, account, pid))


@exam.post("/papers", summary="创建试卷（组卷：题目 + 分值）", dependencies=[Depends(require_perm("training:manage"))])
def create_paper(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_paper(db, account, payload)})


@exam.put("/papers/{pid}", summary="编辑试卷（题目全量覆盖）", dependencies=[Depends(require_perm("training:manage"))])
def update_paper(pid: int, payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.update_paper(db, account, pid, payload))


@exam.post("/papers/{pid}/publish", summary="发布试卷", dependencies=[Depends(require_perm("training:manage"))])
def publish_paper(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.publish_paper(db, account, pid))


@exam.delete("/papers/{pid}", summary="删除试卷", dependencies=[Depends(require_perm("training:manage"))])
def delete_paper(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_paper(db, account, pid))


# ---------- 考试记录 ----------

@exam.get("/records", summary="考试记录（分页 + 本月次数）")
def list_records(paging: tuple[int, int] = Depends(page_params),
                 account=Depends(get_current_account), db: Session = Depends(get_db)):
    page, page_size = paging
    return resp.ok(service.list_records(db, account, page, page_size))
