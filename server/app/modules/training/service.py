"""安全培训服务：课程库、培训任务（人群快照+期限）、题库与试卷。

演练联动（SUBMIT → 自动生成培训任务）TODO(二期) 由事件消费者触发。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.deps import apply_data_scope

from .models import (
    Course, ExamPaper, ExamPaperQuestion, ExamQuestion, ExamRecord,
    TrainingAssignment, TrainingTask,
)

_DIFF_MAP = {1: "easy", 2: "mid", 3: "hard"}


# ---------- 课程库 ----------

def list_courses(db, account):
    """课程列表：聚合学习人数与平均进度（一次查询，避免 N+1）。"""
    stmt = select(Course).order_by(Course.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=Course.created_by,
                            allow_null_owner=True)  # 内置课程 created_by IS NULL 全员可见
    courses = db.scalars(stmt).all()
    stats: dict[int, tuple] = {}
    if courses:
        rows = db.execute(
            select(
                TrainingAssignment.course_id,
                func.count(func.distinct(TrainingAssignment.user_id)),
                func.avg(TrainingAssignment.progress),
            ).group_by(TrainingAssignment.course_id)
        ).all()
        stats = {cid: (learners, avg) for cid, learners, avg in rows}
    return [
        {
            "id": c.id,
            "title": c.title,
            "type": c.type or "video",
            "duration": int(c.duration_min or 0),
            "level": c.level or "easy",
            "material": c.material or "",
            "learners": int(stats.get(c.id, (0, 0))[0] or 0),
            "completion": int(round(stats.get(c.id, (0, 0))[1] or 0)),
            "description": c.description or "",
        }
        for c in courses
    ]


def create_course(db, account, payload: dict) -> int:
    """新建自定义课程（人工创建，直接 approved 入库）。"""
    title = payload.get("name") or payload.get("title") or "未命名课程"
    course = Course(
        title=title,
        type=payload.get("type") or "video",
        duration_min=int(payload.get("duration") or 20),
        description=payload.get("desc"),
        level=payload.get("level") or "easy",
        source="custom",
        status="approved",
        created_by=account.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    record_audit(db, account=account, module="training", action="create_course",
                 target_type="course", target_id=str(course.id), detail={"title": title})
    return course.id


# ---------- 培训任务 ----------

def _parse_deadline(value) -> datetime:
    """期限支持 datetime/ISO 字符串；缺失或解析失败默认 7 天后。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            pass
    return datetime.now() + timedelta(days=7)


def list_tasks(db, account):
    """培训任务列表：完成度按学习任务聚合，状态按期限/完成情况计算。"""
    stmt = select(TrainingTask).order_by(TrainingTask.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=TrainingTask.created_by,
                            allow_null_owner=True)
    tasks = db.scalars(stmt).all()
    items = []
    now = datetime.now()
    for t in tasks:
        assignments = db.scalars(
            select(TrainingAssignment).where(TrainingAssignment.task_id == t.id)
        ).all()
        course_title = ""
        if assignments:
            course = db.get(Course, assignments[0].course_id)
            course_title = course.title if course else ""
        audience = t.audience or {}
        target = audience.get("label") or ", ".join(str(k) for k in audience.keys()) or ""
        done = sum(1 for a in assignments if a.status == "completed")
        started = sum(1 for a in assignments if int(a.progress or 0) > 0)
        avg = int(round(sum(int(a.progress or 0) for a in assignments) / len(assignments))) if assignments else 0
        if t.status == "closed" or (assignments and done == len(assignments)):
            status = "completed"
        elif t.deadline_at and t.deadline_at < now:
            status = "expired"
        else:
            status = "running"
        items.append({
            "name": t.name,
            "course": course_title,
            "target": target,
            "count": len(assignments),
            "start": t.created_at.strftime("%Y-%m-%d") if t.created_at else "",
            "end": t.deadline_at.strftime("%Y-%m-%d") if t.deadline_at else "",
            "started": started,
            "done": done,
            "progress": avg,
            "status": status,
        })
    return items


def create_task(db, account, payload: dict) -> int:
    """创建培训任务：保存人群快照 + 期限，按 user_ids 展开学习任务。"""
    audience = payload.get("targets") or payload.get("audience") or {}
    task = TrainingTask(
        name=payload.get("name") or "未命名培训",
        source="manual",
        campaign_id=payload.get("campaign_id"),
        audience=audience,
        deadline_at=_parse_deadline(payload.get("deadline")),
        status="active",
        created_by=account.id,
    )
    db.add(task)
    db.flush()

    course_id = payload.get("courseId") or payload.get("course_id")
    user_ids = payload.get("user_ids") or audience.get("user_ids") or []
    if course_id:  # 未选课程时仅建任务，不生成学习任务
        for uid in user_ids:
            db.add(TrainingAssignment(
                task_id=task.id, course_id=course_id, user_id=int(uid),
                progress=0, status="pending",
            ))
    db.commit()
    record_audit(db, account=account, module="training", action="create_task",
                 target_type="training_task", target_id=str(task.id),
                 detail={"name": task.name, "count": len(user_ids)})
    return task.id


# ---------- 题库与试卷 ----------

def list_questions(db, account):
    """题库列表：不下发 answer，难度映射为展示值。"""
    stmt = select(ExamQuestion).order_by(ExamQuestion.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=ExamQuestion.created_by,
                            allow_null_owner=True)
    questions = db.scalars(stmt).all()
    items = []
    for q in questions:
        course_title = ""
        if q.course_id:
            course = db.get(Course, q.course_id)
            course_title = course.title if course else ""
        items.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
            "options": q.options or [],
            "diff": _DIFF_MAP.get(q.difficulty, "mid"),
            "course": course_title,
        })
    return items


def list_papers(db, account):
    """试卷列表：按题型统计题量与总分，附带发布（考试）次数。"""
    stmt = select(ExamPaper).order_by(ExamPaper.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=ExamPaper.created_by,
                            allow_null_owner=True)
    papers = db.scalars(stmt).all()
    items = []
    for p in papers:
        rows = db.execute(
            select(ExamQuestion.type, func.count(), func.sum(ExamPaperQuestion.score))
            .join(ExamPaperQuestion, ExamPaperQuestion.question_id == ExamQuestion.id)
            .where(ExamPaperQuestion.paper_id == p.id)
            .group_by(ExamQuestion.type)
        ).all()
        type_cnt = {r[0]: int(r[1] or 0) for r in rows}
        total = int(sum(r[2] or 0 for r in rows))
        publish_count = int(db.scalar(
            select(func.count()).select_from(ExamRecord).where(ExamRecord.paper_id == p.id)
        ) or 0)
        items.append({
            "name": p.title,
            "single": type_cnt.get("single", 0),
            "multi": type_cnt.get("multi", 0),
            "judge": type_cnt.get("judge", 0),
            "total": total,
            "pass": int(p.pass_score or 0),
            "passPct": int(p.pass_score or 0),
            "publishCount": publish_count,
        })
    return items
