"""安全培训服务：课程库、培训任务（人群快照+期限）、题库与试卷。

演练联动（SUBMIT → 自动生成培训任务）TODO(二期) 由事件消费者触发。
"""
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.config import settings as app_settings
from app.core.deps import apply_data_scope
from app.core.errors import BizError, ErrorCode

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
        material=payload.get("material") or None,
        cover_url=payload.get("cover_url") or None,
        content_url=payload.get("content_url") or None,
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
        labels = audience.get("labels") or []
        target = audience.get("label") or (", ".join(labels) if isinstance(labels, list) else str(labels)) or ""
        done = sum(1 for a in assignments if a.status == "completed")
        started = sum(1 for a in assignments if int(a.progress or 0) > 0)
        avg = int(round(sum(int(a.progress or 0) for a in assignments) / len(assignments))) if assignments else 0
        if t.status == "closed":
            status = "closed"
        elif assignments and done == len(assignments):
            status = "completed"
        elif t.deadline_at and t.deadline_at < now:
            status = "expired"
        else:
            status = "running"
        items.append({
            "id": t.id,
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
    """创建培训任务：保存人群快照 + 期限，按部门/用户/全员展开学习任务。

    audience 结构：{labels: [str], dept_ids: [int], user_ids: [int], all: bool}
    """
    from app.modules.org.models import EmpUser  # 延迟导入避免循环

    audience = payload.get("targets") or payload.get("audience") or {}
    if isinstance(audience, list):  # 兼容旧格式：字符串列表（部门/分组编码）
        audience = {"labels": audience}
    labels = audience.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]

    task = TrainingTask(
        name=payload.get("name") or "未命名培训",
        source="manual",
        campaign_id=payload.get("campaign_id"),
        audience={
            "labels": labels,
            "dept_ids": audience.get("dept_ids") or [],
            "user_ids": audience.get("user_ids") or [],
            "all": bool(audience.get("all")),
        },
        deadline_at=_parse_deadline(payload.get("deadline")),
        status="active",
        created_by=account.id,
    )
    db.add(task)
    db.flush()

    course_id = payload.get("courseId") or payload.get("course_id")
    if course_id:  # 未选课程时仅建任务，不生成学习任务
        uids: set[int] = {int(u) for u in (audience.get("user_ids") or [])}
        if audience.get("all"):
            uids.update(db.scalars(select(EmpUser.id)).all())
        dept_ids = [int(d) for d in (audience.get("dept_ids") or [])]
        if dept_ids:
            uids.update(db.scalars(select(EmpUser.id).where(EmpUser.dept_id.in_(dept_ids))).all())
        for uid in sorted(uids):
            db.add(TrainingAssignment(
                task_id=task.id, course_id=course_id, user_id=uid,
                progress=0, status="pending",
            ))
    db.commit()
    record_audit(db, account=account, module="training", action="create_task",
                 target_type="training_task", target_id=str(task.id),
                 detail={"name": task.name, "count": len(uids) if course_id else 0})
    return task.id


def get_task(db, account, task_id: int) -> dict:
    """任务详情：基本信息 + 人员学习明细（批量补部门，避免 N+1）。"""
    from app.modules.org.models import EmpDept, EmpUser

    task = db.get(TrainingTask, task_id)
    if task is None:
        raise BizError(ErrorCode.NOT_FOUND, "培训任务不存在")
    assignments = db.scalars(
        select(TrainingAssignment).where(TrainingAssignment.task_id == task_id)
        .order_by(TrainingAssignment.id)
    ).all()
    user_ids = {a.user_id for a in assignments}
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    course_title = ""
    if assignments:
        course = db.get(Course, assignments[0].course_id)
        course_title = course.title if course else ""

    audience = task.audience or {}
    label = audience.get("label") or (", ".join(audience.get("labels") or []) or "")
    return {
        "id": task.id,
        "name": task.name,
        "course": course_title,
        "target": label,
        "deadline": task.deadline_at.strftime("%Y-%m-%d %H:%M") if task.deadline_at else "",
        "status": task.status,
        "people": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "name": (users[a.user_id].name if a.user_id in users else f"员工#{a.user_id}"),
                "dept": depts[users[a.user_id].dept_id].name
                if a.user_id in users and users[a.user_id].dept_id in depts else "",
                "progress": int(a.progress or 0),
                "status": a.status,
                "completed_at": a.completed_at.strftime("%Y-%m-%d %H:%M") if a.completed_at else "",
            }
            for a in assignments
        ],
    }


def close_task(db, account, task_id: int):
    """关闭培训任务（status=closed），未完成学员保留明细。"""
    task = db.get(TrainingTask, task_id)
    if task is None:
        raise BizError(ErrorCode.NOT_FOUND, "培训任务不存在")
    task.status = "closed"
    db.commit()
    record_audit(db, account=account, module="training", action="close_task",
                 target_type="training_task", target_id=str(task_id),
                 detail={"name": task.name})
    return None


def remind_task(db, account, task_id: int) -> dict:
    """催办：统计未完成人数并审计（真实通知渠道二期接入）。"""
    task = db.get(TrainingTask, task_id)
    if task is None:
        raise BizError(ErrorCode.NOT_FOUND, "培训任务不存在")
    undone = int(db.scalar(
        select(func.count()).select_from(TrainingAssignment).where(
            TrainingAssignment.task_id == task_id,
            TrainingAssignment.status != "completed",
        )
    ) or 0)
    record_audit(db, account=account, module="training", action="remind_task",
                 target_type="training_task", target_id=str(task_id),
                 detail={"name": task.name, "undone": undone})
    return {"undone": undone}


def delete_task(db, account, task_id: int):
    """删除培训任务（连带学习任务明细）。"""
    task = db.get(TrainingTask, task_id)
    if task is None:
        raise BizError(ErrorCode.NOT_FOUND, "培训任务不存在")
    db.execute(TrainingAssignment.__table__.delete().where(
        TrainingAssignment.task_id == task_id))
    db.delete(task)
    db.commit()
    record_audit(db, account=account, module="training", action="delete_task",
                 target_type="training_task", target_id=str(task_id),
                 detail={"name": task.name})
    return None


def export_task_xlsx(db, account, task_id: int) -> tuple[bytes, str]:
    """导出任务人员明细 Excel（openpyxl 同步生成）。"""
    from io import BytesIO

    from openpyxl import Workbook

    from app.modules.org.models import EmpDept, EmpUser

    task = db.get(TrainingTask, task_id)
    if task is None:
        raise BizError(ErrorCode.NOT_FOUND, "培训任务不存在")
    assignments = db.scalars(
        select(TrainingAssignment).where(TrainingAssignment.task_id == task_id)
        .order_by(TrainingAssignment.id)
    ).all()
    user_ids = {a.user_id for a in assignments}
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    course_title = ""
    if assignments:
        course = db.get(Course, assignments[0].course_id)
        course_title = course.title if course else ""

    wb = Workbook()
    ws = wb.active
    ws.title = "培训任务明细"
    ws.append([f"任务：{task.name}", "", f"课程：{course_title}"])
    ws.append([f"截止：{task.deadline_at.strftime('%Y-%m-%d %H:%M') if task.deadline_at else '-'}", "", ""])
    ws.append([])
    ws.append(["序号", "姓名", "部门", "进度%", "状态", "完成时间"])
    status_text = {"pending": "未开始", "learning": "学习中", "completed": "已完成", "overdue": "已逾期"}
    for i, a in enumerate(assignments, start=1):
        u = users.get(a.user_id)
        ws.append([
            i,
            u.name if u else f"员工#{a.user_id}",
            depts[u.dept_id].name if u and u.dept_id in depts else "",
            int(a.progress or 0),
            status_text.get(a.status, a.status),
            a.completed_at.strftime("%Y-%m-%d %H:%M") if a.completed_at else "",
        ])
    buf = BytesIO()
    wb.save(buf)
    record_audit(db, account=account, module="training", action="export_task",
                 target_type="training_task", target_id=str(task_id),
                 detail={"name": task.name, "rows": len(assignments)})
    return buf.getvalue(), f"培训任务_{task.name}_{task_id}.xlsx"


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


def get_question(db, account, question_id: int) -> dict:
    """题目详情（管理端编辑回填：含答案/解析/关联课程）。"""
    q = db.get(ExamQuestion, question_id)
    if q is None:
        raise BizError(ErrorCode.NOT_FOUND, "题目不存在")
    course_title = ""
    if q.course_id:
        course = db.get(Course, q.course_id)
        course_title = course.title if course else ""
    return {
        "id": q.id,
        "type": q.type,
        "content": q.content,
        "options": q.options or [],
        "answer": q.answer,
        "analysis": q.analysis or "",
        "diff": _DIFF_MAP.get(q.difficulty, "mid"),
        "course_id": q.course_id,
        "course": course_title,
    }


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
            "id": p.id,
            "name": p.title,
            "single": type_cnt.get("single", 0),
            "multi": type_cnt.get("multi", 0),
            "judge": type_cnt.get("judge", 0),
            "total": total,
            "pass": int(p.pass_score or 0),
            "passPct": int(p.pass_score or 0),
            "publishCount": publish_count,
            "status": p.status,
        })
    return items


# ---------- 课程 CRUD ----------

def get_course(db, account, course_id: int) -> dict:
    """课程详情（预览）：基本信息 + 封面/课件地址。"""
    c = db.get(Course, course_id)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND, "课程不存在")
    return {
        "id": c.id,
        "title": c.title,
        "type": c.type,
        "level": c.level,
        "duration": int(c.duration_min or 0),
        "material": c.material or "",
        "description": c.description or "",
        "cover_url": c.cover_url or "",
        "content_url": c.content_url or "",
        "source": c.source,
        "status": c.status,
    }


def update_course(db, account, course_id: int, payload: dict) -> None:
    """编辑课程（名称/类型/难度/时长/描述/课件信息）。"""
    c = db.get(Course, course_id)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND, "课程不存在")
    title = (payload.get("name") or payload.get("title") or "").strip()
    if title:
        c.title = title
    if payload.get("type") in ("video", "article", "pdf", "interactive"):
        c.type = payload["type"]
    if payload.get("level") in ("easy", "mid", "hard"):
        c.level = payload["level"]
    if payload.get("duration"):
        c.duration_min = int(payload["duration"])
    if "desc" in payload:
        c.description = payload["desc"]
    if payload.get("material"):
        c.material = payload["material"]
    if "cover_url" in payload:
        c.cover_url = payload["cover_url"] or None
    if "content_url" in payload:
        c.content_url = payload["content_url"] or None
    db.commit()
    record_audit(db, account=account, module="training", action="update_course",
                 target_type="course", target_id=str(course_id), detail={"title": c.title})
    return None


def delete_course(db, account, course_id: int) -> None:
    """删除课程；被题目/学习任务引用时阻止（防数据悬空）。"""
    c = db.get(Course, course_id)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND, "课程不存在")
    if db.scalar(select(ExamQuestion.id).where(ExamQuestion.course_id == course_id).limit(1)):
        raise BizError(ErrorCode.BIZ_CONFLICT, "课程已被题库题目关联，无法删除")
    if db.scalar(select(TrainingAssignment.id).where(TrainingAssignment.course_id == course_id).limit(1)):
        raise BizError(ErrorCode.BIZ_CONFLICT, "课程已被培训任务分配，无法删除")
    db.delete(c)
    db.commit()
    record_audit(db, account=account, module="training", action="delete_course",
                 target_type="course", target_id=str(course_id), detail={"title": c.title})
    return None


# ---------- 课件上传 ----------

# 扩展名白名单：cover=封面图片；content=课件文档/音视频
_UPLOAD_ALLOWED = {
    "cover": {"png", "jpg", "jpeg", "webp", "gif"},
    "content": {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt",
                "mp4", "webm", "mov", "mp3", "wav"},
}
_UPLOAD_MAX = {"cover": 2 * 1024 * 1024, "content": 100 * 1024 * 1024}


def upload_course_file(db, account, file, file_type: str) -> dict:
    """上传课程封面/课件到本地静态目录（与 logo 上传同模式；MinIO 二期接入）。

    file_type: cover=封面图片(≤2MB) / content=课件文档音视频(≤100MB)。
    流式写盘避免大文件占内存；文件名 uuid 化防冲突；返回 /static/course/ 访问地址。
    """
    if file_type not in _UPLOAD_ALLOWED:
        raise BizError(ErrorCode.PARAM_INVALID, "upload 类型必须为 cover/content")
    allowed = _UPLOAD_ALLOWED[file_type]
    ext = (Path(file.filename or "").suffix or "").lower().lstrip(".")
    if ext not in allowed:
        raise BizError(ErrorCode.PARAM_INVALID,
                       f"{'封面' if file_type == 'cover' else '课件'}仅支持 {'/'.join(sorted(allowed))}")

    dest_dir = Path(app_settings.static_dir) / "course"
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    dest = dest_dir / filename
    max_size = _UPLOAD_MAX[file_type]
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    raise BizError(ErrorCode.PARAM_INVALID,
                                   f"{'封面' if file_type == 'cover' else '课件'}不能超过 {max_size // (1024 * 1024)}MB")
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise BizError(ErrorCode.PARAM_INVALID, "上传文件为空")

    url = f"/static/course/{filename}"
    record_audit(db, account=account, module="training", action="upload_course_file",
                 target_type="course_file", target_id=url,
                 detail={"type": file_type, "size": size, "original": file.filename})
    return {"url": url, "size": size, "filename": file.filename or filename}


# ---------- 题目 CRUD ----------

def _validate_question(payload: dict) -> None:
    """题型/选项/答案一致性校验。"""
    qtype = payload.get("type")
    if qtype not in ("single", "multi", "judge"):
        raise BizError(ErrorCode.PARAM_INVALID, "题型必须为 single/multi/judge")
    content = (payload.get("content") or "").strip()
    if not content:
        raise BizError(ErrorCode.PARAM_INVALID, "题干不能为空")
    if qtype == "judge":
        answer = (payload.get("answer") or "").strip().upper()
        if answer not in ("A", "B"):
            raise BizError(ErrorCode.PARAM_INVALID, "判断题答案只能为 A（正确）/ B（错误）")
    else:
        options = payload.get("options") or []
        if not isinstance(options, list) or len(options) < 2:
            raise BizError(ErrorCode.PARAM_INVALID, "选择题至少提供 2 个选项")
        answer = (payload.get("answer") or "").strip().upper()
        letters = {chr(ord("A") + i) for i in range(len(options))}
        if not answer or any(ch not in letters for ch in answer.split(",")):
            raise BizError(ErrorCode.PARAM_INVALID, "答案必须为选项字母（如 A 或 A,B）")


def create_question(db, account, payload: dict) -> int:
    """新建题目：答案明文入库（非口令类数据，无红线约束）。"""
    _validate_question(payload)
    difficulty = {"easy": 1, "mid": 2, "hard": 3}.get(payload.get("diff"), 2)
    q = ExamQuestion(
        type=payload["type"],
        content=(payload.get("content") or "").strip(),
        options=payload.get("options") or [],
        answer=(payload.get("answer") or "").strip().upper(),
        analysis=payload.get("analysis") or None,
        difficulty=difficulty,
        course_id=payload.get("course_id"),
        created_by=account.id,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    record_audit(db, account=account, module="training", action="create_question",
                 target_type="exam_question", target_id=str(q.id),
                 detail={"type": q.type, "content": q.content[:50]})
    return q.id


def update_question(db, account, question_id: int, payload: dict) -> None:
    """编辑题目（全量覆盖字段）。"""
    q = db.get(ExamQuestion, question_id)
    if q is None:
        raise BizError(ErrorCode.NOT_FOUND, "题目不存在")
    _validate_question(payload)
    q.type = payload["type"]
    q.content = (payload.get("content") or "").strip()
    q.options = payload.get("options") or []
    q.answer = (payload.get("answer") or "").strip().upper()
    q.analysis = payload.get("analysis") or None
    q.difficulty = {"easy": 1, "mid": 2, "hard": 3}.get(payload.get("diff"), 2)
    q.course_id = payload.get("course_id")
    db.commit()
    record_audit(db, account=account, module="training", action="update_question",
                 target_type="exam_question", target_id=str(question_id))
    return None


def delete_question(db, account, question_id: int) -> None:
    """删除题目；被试卷引用时阻止。"""
    q = db.get(ExamQuestion, question_id)
    if q is None:
        raise BizError(ErrorCode.NOT_FOUND, "题目不存在")
    if db.scalar(select(ExamPaperQuestion.paper_id).where(
            ExamPaperQuestion.question_id == question_id).limit(1)):
        raise BizError(ErrorCode.BIZ_CONFLICT, "题目已被试卷引用，无法删除")
    db.delete(q)
    db.commit()
    record_audit(db, account=account, module="training", action="delete_question",
                 target_type="exam_question", target_id=str(question_id))
    return None


# ---------- 试卷 CRUD ----------

def create_paper(db, account, payload: dict) -> int:
    """创建试卷：名称/分数线/时长 + 题目列表[{id, score}]。"""
    title = (payload.get("title") or "").strip()
    if not title:
        raise BizError(ErrorCode.PARAM_INVALID, "试卷名称不能为空")
    questions = payload.get("questions") or []
    if not questions:
        raise BizError(ErrorCode.PARAM_INVALID, "请至少选择一道题目")
    qids = [int(q["id"]) for q in questions]
    exist = set(db.scalars(select(ExamQuestion.id).where(ExamQuestion.id.in_(qids))).all())
    missing = [i for i in qids if i not in exist]
    if missing:
        raise BizError(ErrorCode.PARAM_INVALID, f"题目不存在：{missing}")

    paper = ExamPaper(
        title=title,
        pass_score=int(payload.get("pass_score") or 60),
        duration_min=int(payload.get("duration_min") or 30),
        status="draft",
        created_by=account.id,
    )
    db.add(paper)
    db.flush()
    for q in questions:
        db.add(ExamPaperQuestion(
            paper_id=paper.id, question_id=int(q["id"]),
            score=int(q.get("score") or 5),
        ))
    db.commit()
    record_audit(db, account=account, module="training", action="create_paper",
                 target_type="exam_paper", target_id=str(paper.id),
                 detail={"title": title, "questions": len(questions)})
    return paper.id


def get_paper(db, account, paper_id: int) -> dict:
    """试卷详情（预览）：题目完整列表（管理端含答案/解析）。"""
    p = db.get(ExamPaper, paper_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "试卷不存在")
    rows = db.execute(
        select(ExamQuestion, ExamPaperQuestion.score)
        .join(ExamPaperQuestion, ExamPaperQuestion.question_id == ExamQuestion.id)
        .where(ExamPaperQuestion.paper_id == paper_id)
        .order_by(ExamPaperQuestion.question_id)
    ).all()
    total = int(sum(r[1] or 0 for r in rows))
    return {
        "id": p.id,
        "name": p.title,
        "pass": int(p.pass_score or 0),
        "duration": int(p.duration_min or 0),
        "status": p.status,
        "total": total,
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "content": q.content,
                "options": q.options or [],
                "answer": q.answer,
                "analysis": q.analysis or "",
                "score": int(score or 0),
                "diff": {1: "easy", 2: "mid", 3: "hard"}.get(q.difficulty, "mid"),
            }
            for q, score in rows
        ],
    }


def update_paper(db, account, paper_id: int, payload: dict) -> None:
    """编辑试卷：基本信息 + 题目全量覆盖。"""
    p = db.get(ExamPaper, paper_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "试卷不存在")
    title = (payload.get("title") or "").strip()
    if title:
        p.title = title
    if payload.get("pass_score"):
        p.pass_score = int(payload["pass_score"])
    if payload.get("duration_min"):
        p.duration_min = int(payload["duration_min"])

    questions = payload.get("questions")
    if questions is not None:
        qids = [int(q["id"]) for q in questions]
        exist = set(db.scalars(select(ExamQuestion.id).where(ExamQuestion.id.in_(qids))).all())
        missing = [i for i in qids if i not in exist]
        if missing:
            raise BizError(ErrorCode.PARAM_INVALID, f"题目不存在：{missing}")
        db.execute(ExamPaperQuestion.__table__.delete().where(
            ExamPaperQuestion.paper_id == paper_id))
        for q in questions:
            db.add(ExamPaperQuestion(
                paper_id=paper_id, question_id=int(q["id"]),
                score=int(q.get("score") or 5),
            ))
    db.commit()
    record_audit(db, account=account, module="training", action="update_paper",
                 target_type="exam_paper", target_id=str(paper_id),
                 detail={"title": p.title})
    return None


def publish_paper(db, account, paper_id: int) -> None:
    """发布试卷：status → published + 审计（考试分发二期接任务/学员端）。"""
    p = db.get(ExamPaper, paper_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "试卷不存在")
    p.status = "published"
    db.commit()
    record_audit(db, account=account, module="training", action="publish_paper",
                 target_type="exam_paper", target_id=str(paper_id), detail={"title": p.title})
    return None


def delete_paper(db, account, paper_id: int) -> None:
    """删除试卷（考试记录保留，试卷题目关联级联删除）。"""
    p = db.get(ExamPaper, paper_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "试卷不存在")
    db.execute(ExamPaperQuestion.__table__.delete().where(
        ExamPaperQuestion.paper_id == paper_id))
    db.delete(p)
    db.commit()
    record_audit(db, account=account, module="training", action="delete_paper",
                 target_type="exam_paper", target_id=str(paper_id), detail={"title": p.title})
    return None


# ---------- 考试记录 ----------

def list_records(db, account, page=1, page_size=20) -> dict:
    """考试记录：分页 + 本月次数；批量补试卷/员工/部门信息。"""
    from app.modules.org.models import EmpDept, EmpUser

    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = int(db.scalar(select(func.count()).select_from(ExamRecord)) or 0)
    month_total = int(db.scalar(
        select(func.count()).select_from(ExamRecord).where(ExamRecord.submitted_at >= month_start)
    ) or 0)

    stmt = select(ExamRecord).order_by(ExamRecord.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=ExamRecord.user_id)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    paper_ids = {r.paper_id for r in rows}
    papers = {p.id: p.title for p in db.scalars(select(ExamPaper).where(ExamPaper.id.in_(paper_ids))).all()} if paper_ids else {}
    user_ids = {r.user_id for r in rows}
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d.name for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    return {
        "total": total,
        "monthTotal": month_total,
        "page": page,
        "pageSize": page_size,
        "list": [
            {
                "id": r.id,
                "paper": papers.get(r.paper_id, f"试卷#{r.paper_id}"),
                "user": users[r.user_id].name if r.user_id in users else f"员工#{r.user_id}",
                "dept": depts[users[r.user_id].dept_id]
                if r.user_id in users and users[r.user_id].dept_id in depts else "",
                "score": int(r.score or 0),
                "passed": bool(r.passed),
                "time": (r.submitted_at or r.created_at).strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        ],
    }
