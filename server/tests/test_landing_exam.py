"""学员端培训考试（landing 服务）：/learn/{course_id} 考试入口、答题页无答案泄露、
交卷判分（多选乱序等价）、ExamRecord 落库、首过写回风险画像（培训完成度/风险分）。"""
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.training.models import (
    Course, ExamPaper, ExamPaperQuestion, ExamQuestion, ExamRecord,
)

from landing.main import app as landing_app

TOKEN = "c" * 32
COURSE_ID = 9001
PAPER_ID = 9001
_Q_BASE = 9001

client = TestClient(landing_app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (ExamRecord, ExamPaperQuestion, ExamPaper, ExamQuestion, Course,
                  CampaignTarget, Campaign, EmpRiskProfile, EmpUser, EmpDept):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _seed_exam(db, *, course_id=COURSE_ID, paper_id=PAPER_ID, pass_score=60):
    """种子：课程 + 已发布试卷（单选/多选/判断各一题，每题 5 分）+ 演练与目标员工。"""
    db.add(Course(id=course_id, title="信息安全意识培训", type="article",
                  duration_min=20, description="防钓鱼基础课程", status="published"))
    db.add(ExamQuestion(
        id=_Q_BASE, type="single", content="收到要求点击链接更新工资卡的邮件，应该？",
        options=["A.直接点击链接", "B.回复确认", "C.找HR核实", "D.转发同事"], answer="C",
    ))
    db.add(ExamQuestion(
        id=_Q_BASE + 1, type="multi", content="以下哪些属于常见钓鱼手法？",
        options=["仿冒登录页", "伪造快递短信", "正常会议邀请"], answer="A,B",
    ))
    db.add(ExamQuestion(
        id=_Q_BASE + 2, type="judge", content="有公司logo且域名正确即可放心点击链接。",
        options=[], answer="B",
    ))
    db.add(ExamPaper(id=paper_id, title="中招员工培训考试", pass_score=pass_score,
                     duration_min=30, status="published", course_id=course_id))
    for i in range(3):
        db.add(ExamPaperQuestion(paper_id=paper_id, question_id=_Q_BASE + i, score=5))
    dept = EmpDept(name="测试部", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="中招员工", email="phished@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    campaign = Campaign(name="考试演练", type="mail", creator_id=1,
                        training_policy="redirect", course_ids=[course_id])
    db.add(campaign)
    db.flush()
    db.add(CampaignTarget(campaign_id=campaign.id, user_id=user.id, token=TOKEN))
    db.commit()
    return user.id


# ---------- 学习页：考试入口 ----------

def test_learn_page_shows_exam_card_only_with_valid_token():
    db = SessionLocal()
    _seed_exam(db)
    db.close()
    r = client.get(f"/learn/{COURSE_ID}?token={TOKEN}")
    assert r.status_code == 200
    assert "信息安全意识培训" in r.text
    assert "开始考试" in r.text
    assert f"/learn/{COURSE_ID}/exam?token={TOKEN}" in r.text
    # 无 token：课程可见但无考试入口（fail-closed）
    r2 = client.get(f"/learn/{COURSE_ID}")
    assert r2.status_code == 200
    assert "开始考试" not in r2.text
    assert "请通过演练邮件中的链接进入培训" in r2.text


# ---------- 答题页：无答案泄露 + 鉴权 ----------

def test_exam_page_hides_answers():
    db = SessionLocal()
    _seed_exam(db)
    db.close()
    r = client.get(f"/learn/{COURSE_ID}/exam?token={TOKEN}")
    assert r.status_code == 200
    body = r.text
    assert "中招员工培训考试" in body
    # 题目进 JS 变量，不含 answer 键（答案绝不下发）
    assert '"answer"' not in body
    # 题干与选项文本渲染（textContent，不入 HTML 源码）
    assert "找HR核实" in body
    # 倒计时按试卷时长（duration_min 下发，JS 端换算秒）
    assert "EXAM.duration_min * 60" in body


def test_exam_page_denied_without_or_wrong_token():
    db = SessionLocal()
    _seed_exam(db)
    db.close()
    assert client.get(f"/learn/{COURSE_ID}/exam").status_code == 403
    assert client.get(f"/learn/{COURSE_ID}/exam?token=bad").status_code == 403
    # token 有效但课程不在演练 course_ids → 403
    assert client.get(f"/learn/9999/exam?token={TOKEN}").status_code == 403


def test_exam_page_denied_without_published_paper():
    db = SessionLocal()
    _seed_exam(db)
    # 试卷下架（改 draft）→ 答题页 403；学习页仅提示考试未开放
    db.query(ExamPaper).filter(ExamPaper.id == PAPER_ID).update({"status": "draft"})
    db.commit()
    db.close()
    assert client.get(f"/learn/{COURSE_ID}/exam?token={TOKEN}").status_code == 403
    r = client.get(f"/learn/{COURSE_ID}?token={TOKEN}")
    assert "开始考试" not in r.text and "考试暂未开放" in r.text


# ---------- 交卷判分 ----------

def _submit(answers: dict, token: str = TOKEN) -> dict:
    r = client.post(f"/learn/{COURSE_ID}/exam/submit", data={
        "token": token, "answers": json.dumps(answers),
        "started_at": "2026-08-30T10:00:00",
    })
    assert r.status_code == 200
    return r


def test_exam_submit_pass_writes_record_and_profile():
    db = SessionLocal()
    uid = _seed_exam(db)  # 及格线 60%：全对 15/15 = 100% 通过
    db.close()
    r = _submit({str(_Q_BASE): "C", str(_Q_BASE + 1): "B,A", str(_Q_BASE + 2): "B"})
    assert "✅ 通过" in r.text and "得分" in r.text and "15" in r.text  # 3×5 全对
    db = SessionLocal()
    rec = db.query(ExamRecord).filter(ExamRecord.paper_id == PAPER_ID).first()
    assert rec is not None and rec.user_id == uid and rec.score == 15 and rec.passed == 1
    assert rec.answers == {str(_Q_BASE): "C", str(_Q_BASE + 1): "B,A", str(_Q_BASE + 2): "B"}
    profile = db.get(EmpRiskProfile, uid)
    assert profile is not None
    assert profile.training_completion == Decimal("100.00")
    assert profile.total_score == 60  # 默认 70 − 10，钳制 ≥0
    assert profile.risk_level == 1
    db.close()


def test_exam_submit_repeat_pass_no_double_risk_reduction():
    db = SessionLocal()
    uid = _seed_exam(db)  # 全对 100% ≥ 60% 通过
    db.close()
    answers = {str(_Q_BASE): "C", str(_Q_BASE + 1): "A,B", str(_Q_BASE + 2): "B"}
    _submit(answers)
    _submit(answers)  # 重复通过：记录新增，风险分不再叠加扣减
    db = SessionLocal()
    assert db.query(ExamRecord).filter(ExamRecord.paper_id == PAPER_ID).count() == 2
    assert db.get(EmpRiskProfile, uid).total_score == 60
    db.close()


def test_exam_submit_fail_no_profile():
    db = SessionLocal()
    uid = _seed_exam(db)
    db.close()
    r = _submit({str(_Q_BASE): "A", str(_Q_BASE + 1): "C", str(_Q_BASE + 2): "A"})
    assert "未通过" in r.text
    assert "正确答案" in r.text  # 结果页逐题回顾
    db = SessionLocal()
    rec = db.query(ExamRecord).filter(ExamRecord.paper_id == PAPER_ID).first()
    assert rec is not None and rec.score == 0 and rec.passed == 0
    assert db.get(EmpRiskProfile, uid) is None  # 未通过不动画像
    db.close()


def test_exam_submit_denied_without_valid_token():
    db = SessionLocal()
    _seed_exam(db)
    db.close()
    answers = {str(_Q_BASE): "C", str(_Q_BASE + 1): "A,B", str(_Q_BASE + 2): "B"}
    assert client.post(f"/learn/{COURSE_ID}/exam/submit",
                       data={"token": "bad", "answers": json.dumps(answers)}).status_code == 403
    assert client.post(f"/learn/{COURSE_ID}/exam/submit",
                       data={"answers": json.dumps(answers)}).status_code == 403
    # 非法 answers JSON → 判 0 分而非 500
    assert client.post(f"/learn/{COURSE_ID}/exam/submit",
                       data={"token": TOKEN, "answers": "{oops"}).status_code == 200


def test_exam_partial_score_passes_threshold():
    """及格判定按百分比：pass_score 是及格线（如 40%），卷面总分随题目数变化。"""
    db = SessionLocal()
    _seed_exam(db, pass_score=40)
    db.close()
    r = _submit({str(_Q_BASE): "C", str(_Q_BASE + 1): "C", str(_Q_BASE + 2): "A"})  # 5/15 = 33%
    assert "未通过" in r.text
    r = _submit({str(_Q_BASE): "C", str(_Q_BASE + 1): "A,B", str(_Q_BASE + 2): "A"})  # 10/15 = 67%
    assert "✅ 通过" in r.text
