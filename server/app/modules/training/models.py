"""培训域：课程、培训任务、学习任务、题库、试卷、考试记录。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class Course(Base, TimestampMixin):
    __tablename__ = "course"

    id: Mapped[int] = pk()
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(16), comment="video/article/pdf/interactive")
    duration_min: Mapped[int] = mapped_column(Integer, default=0)
    cover_url: Mapped[str | None] = mapped_column(String(512))
    content_url: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(12), default="builtin", comment="builtin/custom/ai")
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    # 展示列（课程卡片直接消费）
    level: Mapped[str] = mapped_column(String(8), default="easy", comment="easy/mid/hard")
    material: Mapped[str | None] = mapped_column(String(64), comment="课件形态：视频课件/图文+PDF/场景模拟等")


class TrainingTask(Base, TimestampMixin):
    __tablename__ = "training_task"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(12), comment="manual/campaign")
    campaign_id: Mapped[int | None] = mapped_column(BigInteger)
    audience: Mapped[dict] = mapped_column(JSON, comment="人群快照:部门/分组/标签/用户ID")
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="active", comment="active/closed")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class TrainingAssignment(Base):
    __tablename__ = "training_assignment"

    id: Mapped[int] = pk()
    task_id: Mapped[int] = mapped_column(BigInteger, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="0-100")
    status: Mapped[str] = mapped_column(
        String(12), default="pending", comment="pending/learning/completed/overdue"
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ExamQuestion(Base, TimestampMixin):
    __tablename__ = "exam_question"

    id: Mapped[int] = pk()
    type: Mapped[str] = mapped_column(String(8), comment="single/multi/judge")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON)
    answer: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    course_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="关联课程")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class ExamPaper(Base, TimestampMixin):
    __tablename__ = "exam_paper"

    id: Mapped[int] = pk()
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    pass_score: Mapped[int] = mapped_column(Integer, default=60)
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    course_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, comment="关联课程（中招后培训考试按课程定位试卷）")
    publish_audience: Mapped[dict | None] = mapped_column(JSON, comment="发布对象人群快照:all/dept_ids/user_ids+labels")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class ExamPaperQuestion(Base):
    __tablename__ = "exam_paper_question"

    paper_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, default=5)


class ExamRecord(Base, TimestampMixin):
    __tablename__ = "exam_record"

    id: Mapped[int] = pk()
    paper_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    assignment_id: Mapped[int | None] = mapped_column(BigInteger)
    score: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
