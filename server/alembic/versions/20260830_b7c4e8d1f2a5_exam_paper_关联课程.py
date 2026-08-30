"""exam_paper 关联课程：中招后培训考试按课程定位试卷

Revision ID: b7c4e8d1f2a5
Revises: 9454316399a4
Create Date: 2026-08-30 15:00:00.000000

背景：学员端考试（landing 服务 /learn/{course_id}）需要从演练携带的
course_id 定位已发布试卷。原 exam_paper 无课程归属，加 course_id
（可空：人工培训任务的试卷可不挂课程；挂课后中招员工才能在线考试）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c4e8d1f2a5"
down_revision: Union[str, None] = "9454316399a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exam_paper", sa.Column(
        "course_id", sa.BigInteger(), nullable=True,
        comment="关联课程（中招后培训考试按课程定位试卷）"))
    op.create_index("ix_exam_paper_course_id", "exam_paper", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_paper_course_id", table_name="exam_paper")
    op.drop_column("exam_paper", "course_id")
