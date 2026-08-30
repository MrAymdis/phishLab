"""落地页服务（独立演练域名部署）：仿冒页托管、表单捕获、教育弹窗、培训跳转。

红线：口令类字段永不存明文——只记录字段名与输入长度。
演示模式：绑定 8082 端口，开发机 hosts 映射演练域名后即可完整演示
（点击邮件链接 → 仿冒登录页 → 提交 → 按 training_policy 处理）。

提交后行为按演练 training_policy 分支：
  none     → 空白页（仅记录数据，不告知中招）
  popup    → 教育弹窗（可关闭）
  redirect → 302 培训学习页 /learn/{course_id}
"""
import json
import logging
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phishlab.landing")

app = FastAPI(title="PhishLab Landing", docs_url=None)

_EDU_POPUP = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>安全演练提示</title></head>
<body style="margin:0;font-family:sans-serif">
<div id="overlay" style="position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center">
<div style="max-width:480px;width:88%;background:#fff;border-radius:12px;padding:28px 32px;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.2)">
<h2 style="color:#D85A30;margin:0 0 12px">⚠️ 这是一次钓鱼演练</h2>
<p style="color:#555;line-height:1.7;margin:0 0 8px">您刚才差点泄露了密码！请放心，本次为内部安全演练，您输入的内容<b>不会被记录</b>。</p>
<p style="color:#555;line-height:1.7;margin:0 0 20px">请记住三点：核对发件人域名、不点击可疑链接、可疑邮件及时举报。</p>
<button onclick="document.getElementById('overlay').style.display='none'" style="padding:8px 28px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer">知道了</button>
</div></div>
</body></html>"""

_NONE_PAGE = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>提交成功</title></head>
<body style="margin:0"></body></html>"""


def _submit_path(page_path: str) -> str:
    """页面路径 → 提交路径：根路径 / → /submit（避免 //submit）。"""
    return page_path.rstrip("/") + "/submit"


def _render_login_page(title: str, fields: list[dict], page_path: str, token: str = "") -> str:
    """渲染仿冒登录页：标题 + 表单字段 + 轻量指纹采集 JS（提交时回传）。"""
    from app.modules.template.service import FP_SCRIPT
    inputs = []
    for f in fields:
        key = f.get("field_key") or f.get("label") or "field"
        label = f.get("label") or key
        if f.get("sensitive_flag") or "pass" in key.lower():
            inputs.append(
                f'<input type="password" name="{key}" placeholder="{label}" '
                f'style="width:100%;padding:10px;margin:8px 0;border:1px solid #d1d5db;border-radius:6px" />'
            )
        else:
            inputs.append(
                f'<input type="text" name="{key}" placeholder="{label}" '
                f'style="width:100%;padding:10px;margin:8px 0;border:1px solid #d1d5db;border-radius:6px" />'
            )
    fields_html = "\n".join(inputs)
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding-top:80px">
<div style="width:360px;background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.08);padding:32px">
  <h2 style="text-align:center;color:#333;margin:0 0 8px">{title}</h2>
  <p style="text-align:center;color:#888;font-size:12px;margin:0 0 20px">统一身份认证中心</p>
  <form method="post" action="{_submit_path(page_path)}" id="login-form" style="display:flex;flex-direction:column">
    {fields_html}
    <input type="hidden" name="token" value="{token}" />
    <input type="hidden" name="fp" id="fp-input" value="" />
    <button type="submit" style="margin-top:12px;padding:10px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer">登 录</button>
  </form>
  <p style="text-align:center;color:#aaa;font-size:11px;margin-top:16px">© 企业信息安全中心 · 内部系统</p>
</div>
</body></html>""" + FP_SCRIPT


def _render_custom_html(page, slug: str, token: str, submit_base: str = "",
                        custom_path: str = "") -> str:
    """渲染自定义/克隆页面：静态渲染 + 消毒 + 表单重定向 + token/指纹注入，
    逻辑收敛在 template.service.render_cloned_html（预览接口共用，保证一致）。

    submit_base 传演练域名（request.base_url）：克隆页 <base> 指向原站，表单 action
    必须用绝对 URL，否则会被 base 劫持提交到原站域名。
    custom_path 为空时提交端点 = /p/{slug}/submit，非空时 = {custom_path}/submit。"""
    from app.modules.template.service import render_cloned_html

    return render_cloned_html(
        page.html_content or "", slug, token, page.clone_from_url or "",
        submit_base, custom_path,
    )


def _load_page_and_fields(slug: str | None = None,
                          custom_path: str | None = None) -> tuple[object | None, list[dict] | None]:
    """slug 或 custom_path（二选一）→ (LandingPage, 表单字段)；单会话加载（避免同请求两次连接）。

    page 为 None 或字段为空时返回 None/None，由调用方回退默认登录卡片。
    TODO(三期)：接入 Redis 缓存。
    """
    from app.db.session import SessionLocal
    from app.modules.template.models import LandingFormField, LandingPage

    db = SessionLocal()
    try:
        q = db.query(LandingPage)
        page = (q.filter(LandingPage.slug == slug).first() if slug is not None
                else q.filter(LandingPage.custom_path == custom_path).first())
        if page is None:
            return None, None
        fields = [
            {"field_key": f.field_key, "label": f.label or f.field_key,
             "sensitive_flag": f.sensitive_flag}
            for f in db.query(LandingFormField)
            .filter(LandingFormField.page_id == page.id)
            .order_by(LandingFormField.sort).all()
        ]
        return page, fields or None
    finally:
        db.close()


def _load_policy(token: str) -> tuple[str, list | None, str | None]:
    """token → (training_policy, course_ids, training_redirect_url)。

    token 无效/查不到演练时回退 popup（保持教育提示兜底，避免中招员工零提示）。
    """
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignTarget

    if not token:
        return "popup", None, None
    db = SessionLocal()
    try:
        t = db.query(CampaignTarget).filter(CampaignTarget.token == token).first()
        if t is None:
            return "popup", None, None
        c = db.get(Campaign, t.campaign_id)
        if c is None:
            return "popup", None, None
        return c.training_policy or "none", c.course_ids or [], c.training_redirect_url
    finally:
        db.close()


# ---------- 学员端培训考试（redirect 模式 302 落点） ----------

_EXAM_DENIED = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>链接无效</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding-top:80px">
<div style="max-width:480px;background:#fff;border-radius:12px;padding:32px;text-align:center">
<h2 style="color:#D85A30;margin:0 0 12px">链接无效或已过期</h2>
<p style="color:#555;line-height:1.7;margin:0">请通过演练邮件中的链接进入培训。</p>
</div></body></html>"""


def _load_exam_paper(db, course_id: int):
    """课程 → 已发布试卷（多张取最新）；无则 None。"""
    from app.modules.training.models import ExamPaper

    return (db.query(ExamPaper)
            .filter(ExamPaper.course_id == course_id, ExamPaper.status == "published")
            .order_by(ExamPaper.id.desc())
            .first())


def _load_exam_context(db, course_id: int, token: str):
    """token → (campaign, target)；fail-closed：token 无效或课程不在演练 course_ids → None。"""
    from app.modules.campaign.models import Campaign, CampaignTarget

    if not token:
        return None
    t = db.query(CampaignTarget).filter(CampaignTarget.token == token).first()
    if t is None:
        return None
    c = db.get(Campaign, t.campaign_id)
    if c is None or course_id not in (c.course_ids or []):
        return None
    return c, t


def _paper_questions(db, paper):
    """试卷题目按 question_id 排序：(question, score)。考试页与判分共用，保证顺序一致。"""
    from app.modules.training.models import ExamPaperQuestion, ExamQuestion

    return (db.query(ExamQuestion, ExamPaperQuestion.score)
            .join(ExamPaperQuestion, ExamPaperQuestion.question_id == ExamQuestion.id)
            .filter(ExamPaperQuestion.paper_id == paper.id)
            .order_by(ExamQuestion.id)
            .all())


def _option_rows(qtype: str, options: list | None) -> list[tuple[str, str]]:
    """选项 → [(字母, 文本)]。判断题为固定 A 正确/B 错误；
    单选题选项可能带 "A." 前缀（种子数据形态），按位置剥离。"""
    letters = "ABCDEFGH"
    if qtype == "judge":
        return [("A", "正确"), ("B", "错误")]
    rows = []
    for i, opt in enumerate(options or []):
        letter = letters[i]
        text = str(opt)
        if (qtype == "single" and len(text) > 2 and text[1] == "."
                and text[0].upper() == letter):
            text = text[2:].lstrip()
        rows.append((letter, text))
    return rows


def _answer_display(qtype: str, ans: str) -> str:
    """答案展示：判断题的字母补语义（A→正确/B→错误），其余原样字母。"""
    ans = (ans or "").strip()
    if not ans:
        return "未作答"
    if qtype == "judge":
        return f"{ans.upper()}（{'正确' if ans.upper().startswith('A') else '错误'}）"
    return ans.upper()


def _norm_multi(ans: str) -> str:
    return ",".join(sorted(p.strip().upper() for p in ans.split(",") if p.strip()))


def _grade(paper_questions, user_answers: dict) -> tuple[int, list[dict]]:
    """服务端判分（不信任客户端）：多选按字母集合比较（乱序等价），单选/判断按字母。"""
    total = 0
    details = []
    for q, score in paper_questions:
        correct = (q.answer or "").strip()
        user = str(user_answers.get(str(q.id), "") or "").strip()
        if q.type == "multi":
            ok = bool(correct) and _norm_multi(user) == _norm_multi(correct)
        else:
            ok = bool(correct) and user.upper() == correct.upper()
        if ok:
            total += score
        details.append({
            "id": q.id, "type": q.type, "content": q.content,
            "options": q.options or [], "analysis": q.analysis or "",
            "user_answer": user, "correct": correct, "score": score, "ok": ok,
        })
    return total, details


def _render_exam_result(paper, total: int, pct: int, passed: bool, details: list[dict],
                        course_id: int, token: str) -> str:
    """交卷结果页：得分/是否通过 + 逐题回顾（题面、作答、正确答案、解析）。"""
    import html

    esc = html.escape
    verdict = ("<span style='color:#1D9E75'>✅ 通过</span>"
               if passed else "<span style='color:#D85A30'>❌ 未通过（及格线 {0}%）</span>".format(paper.pass_score))
    rows = []
    for i, d in enumerate(details, 1):
        rows.append(f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:10px 0;text-align:left">
  <p style="margin:0 0 8px;color:#333;font-weight:600">{i}. {esc(d['content'])}</p>
  <p style="margin:0 0 4px;color:#888;font-size:12px">你的作答：{esc(_answer_display(d['type'], d['user_answer']))}
     ｜ 正确答案：{esc(_answer_display(d['type'], d['correct']))} ｜ 得分：{d['score'] if d['ok'] else 0}/{d['score']}</p>
  {f"<p style='margin:0;color:#555;font-size:13px;line-height:1.7'>解析：{esc(d['analysis'])}</p>" if d['analysis'] else ""}
</div>""")
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>考试结果</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding:40px 0">
<div style="width:680px;max-width:94%;background:#fff;border-radius:12px;padding:28px 32px">
  <h2 style="text-align:center;color:#333;margin:0 0 4px">{esc(paper.title)} · 考试结果</h2>
  <p style="text-align:center;margin:0 0 16px">得分 <b style="font-size:22px;color:#378ADD">{total}</b> 分（{pct}%）　{verdict}</p>
  {''.join(rows)}
  <p style="text-align:center;margin:16px 0 0"><a href="/learn/{course_id}?token={quote(token)}"
     style="color:#378ADD;text-decoration:none">← 返回课程</a></p>
</div></body></html>"""


@app.get("/learn/{course_id}", response_class=HTMLResponse)
def learn(course_id: int, token: str = ""):
    """员工端培训学习页（redirect 模式 302 落点）：课程信息 + 已发布试卷考试入口。

    token 有效且课程在演练 course_ids 内才展示考试卡片（fail-closed）。"""
    import html

    from app.db.session import SessionLocal
    from app.modules.training.models import Course

    esc = html.escape
    db = SessionLocal()
    try:
        c = db.get(Course, course_id)
        ctx = _load_exam_context(db, course_id, token)
        paper = _load_exam_paper(db, course_id) if ctx else None
    finally:
        db.close()
    if c is None:
        return HTMLResponse("Not Found", status_code=404)
    desc = c.description or f"课件形态：{c.material or c.type} · 时长 {c.duration_min} 分钟"
    if paper is not None:
        exam_card = f"""
<div style="margin-top:20px;padding:16px;border:1px solid #d6e7f7;border-radius:10px;background:#f2f8fe;text-align:left">
  <p style="margin:0 0 6px;font-weight:600;color:#333">📝 {esc(paper.title)}</p>
  <p style="margin:0 0 12px;color:#888;font-size:12px">及格线 {paper.pass_score}%（按卷面得分换算）· 限时 {paper.duration_min} 分钟</p>
  <a href="/learn/{course_id}/exam?token={quote(token)}"
     style="display:inline-block;padding:8px 26px;background:#378ADD;color:#fff;border-radius:6px;text-decoration:none;font-size:14px">开始考试</a>
</div>"""
    else:
        hint = ("课程学习中，考试暂未开放。" if ctx
                else "请通过演练邮件中的链接进入培训。")
        exam_card = f'<p style="color:#999;font-size:12px;margin-top:20px">{hint}</p>'
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>{esc(c.title)} · 安全培训</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding-top:80px">
<div style="max-width:520px;width:92%;background:#fff;border-radius:12px;padding:32px">
<h2 style="color:#1D9E75;margin:0 0 8px">✅ 您已进入安全培训</h2>
<p style="color:#333;font-size:16px;font-weight:600;margin:0 0 8px">{esc(c.title)}</p>
<p style="color:#555;font-size:13px;line-height:1.7;margin:0">{esc(desc)}</p>
{exam_card}
</div></body></html>""")


@app.get("/learn/{course_id}/exam", response_class=HTMLResponse)
def exam_page(course_id: int, token: str = ""):
    """在线答题页：题目（不含答案）嵌入 JS 变量，倒计时交卷。

    题目内容走 textContent 渲染 + JSON 中 </ 转义，杜绝 XSS。"""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        ctx = _load_exam_context(db, course_id, token)
        paper = _load_exam_paper(db, course_id) if ctx else None
        questions = (_paper_questions(db, paper) if paper is not None else [])
        exam_json = None
        if paper is not None:
            exam_json = json.dumps({
                "paper_id": paper.id, "title": paper.title,
                "pass_score": paper.pass_score, "duration_min": paper.duration_min,
                "questions": [
                    {"id": q.id, "type": q.type, "content": q.content,
                     "options": _option_rows(q.type, q.options), "score": score}
                    for q, score in questions
                ],
            }, ensure_ascii=False).replace("</", "<\\/")
    finally:
        db.close()
    if ctx is None or paper is None or exam_json is None:
        return HTMLResponse(_EXAM_DENIED, status_code=403)
    import html

    esc = html.escape
    token_json = json.dumps(token, ensure_ascii=False).replace("</", "<\\/")
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>{esc(paper.title)}</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding:32px 0">
<div style="width:680px;max-width:94%;background:#fff;border-radius:12px;padding:28px 32px">
  <h2 style="margin:0 0 4px;color:#333">{esc(paper.title)}</h2>
  <p style="margin:0 0 18px;color:#888;font-size:13px">及格线 {paper.pass_score}% · 倒计时 <b id="clock" style="color:#D85A30">--:--</b></p>
  <div id="questions"></div>
  <button id="submit-btn" style="display:block;margin:18px auto 0;padding:10px 44px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:15px;cursor:pointer">交 卷</button>
</div>
<script>
window.EXAM = {exam_json};
window.EXAM_SUBMIT_URL = "/learn/{course_id}/exam/submit";
window.EXAM_TOKEN = {token_json};
(function(){{
  var letters = "ABCDEFGH";
  var typeNames = {{single: "单选题", multi: "多选题", judge: "判断题"}};
  var answers = {{}};
  var remain = EXAM.duration_min * 60;
  function fmt(s) {{ var m = Math.floor(s / 60), ss = s % 60; return (m < 10 ? "0" : "") + m + ":" + (ss < 10 ? "0" : "") + ss; }}
  document.getElementById("clock").textContent = fmt(remain);
  EXAM.questions.forEach(function(q, idx){{
    var box = document.createElement("div");
    box.style.cssText = "border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:10px 0";
    var head = document.createElement("p");
    head.style.cssText = "margin:0 0 8px;color:#333;font-weight:600";
    head.textContent = (idx + 1) + ". [" + (typeNames[q.type] || q.type) + "] " + q.content + "（" + q.score + " 分）";
    box.appendChild(head);
    q.options.forEach(function(opt){{
      var label = document.createElement("label");
      label.style.cssText = "display:block;padding:6px 10px;margin:4px 0;border:1px solid #e5e7eb;border-radius:6px;cursor:pointer;color:#555;font-size:14px";
      var input = document.createElement("input");
      input.type = q.type === "multi" ? "checkbox" : "radio";
      input.name = "q" + q.id;
      input.value = opt[0];
      input.style.marginRight = "8px";
      input.addEventListener("change", function(){{
        if (q.type === "multi") {{
          var picked = box.querySelectorAll("input:checked");
          var arr = []; picked.forEach(function(p) {{ arr.push(p.value); }});
          answers[q.id] = arr.sort().join(",");
        }} else {{
          answers[q.id] = input.value;
        }}
      }});
      label.appendChild(input);
      label.appendChild(document.createTextNode(opt[0] + ". " + opt[1]));
      box.appendChild(label);
    }});
    document.getElementById("questions").appendChild(box);
  }});
  function submit(){{
    var form = document.createElement("form");
    form.method = "post";
    form.action = EXAM_SUBMIT_URL;
    var fields = {{token: EXAM_TOKEN, answers: JSON.stringify(answers), started_at: new Date().toISOString()}};
    Object.keys(fields).forEach(function(k){{
      var h = document.createElement("input");
      h.type = "hidden"; h.name = k; h.value = fields[k];
      form.appendChild(h);
    }});
    document.body.appendChild(form);
    form.submit();
  }}
  var timer = setInterval(function(){{
    remain -= 1;
    document.getElementById("clock").textContent = fmt(Math.max(remain, 0));
    if (remain <= 0) {{ clearInterval(timer); submit(); }}
  }}, 1000);
  document.getElementById("submit-btn").addEventListener("click", submit);
}})();
</script>
</body></html>""")


@app.post("/learn/{course_id}/exam/submit", response_class=HTMLResponse)
async def exam_submit(course_id: int, request: Request):
    """交卷判分：服务端按答案字母判分（多选乱序等价）→ ExamRecord 入库；
    首次通过写回风险画像（培训完成度 100、风险分 -10 钳制 ≥0）。"""
    import html
    from datetime import datetime, timezone

    from app.db.session import SessionLocal
    from app.modules.org.models import EmpRiskProfile
    from app.modules.org.service import _risk_level_of
    from app.modules.training.models import ExamRecord
    from sqlalchemy import select

    form = await request.form()
    token = str(form.get("token") or "")
    db = SessionLocal()
    try:
        ctx = _load_exam_context(db, course_id, token)
        paper = _load_exam_paper(db, course_id) if ctx else None
        questions = _paper_questions(db, paper) if paper is not None else []
        if ctx is None or paper is None:
            return HTMLResponse(_EXAM_DENIED, status_code=403)
        _, target = ctx
        try:
            user_answers = json.loads(str(form.get("answers") or "{}"))
            if not isinstance(user_answers, dict):
                user_answers = {}
            user_answers = {str(k): str(v)[:16] for k, v in user_answers.items()}
        except (json.JSONDecodeError, TypeError):
            user_answers = {}
        total, details = _grade(questions, user_answers)
        # 及格判定：pass_score 为百分比（列表 API 同名 passPct），卷面总分随题目数变化
        max_score = sum(score for _, score in questions) or 0
        pct = round(total * 100 / max_score) if max_score else 0
        passed = max_score > 0 and pct >= paper.pass_score
        started_at = None
        try:
            started_at = datetime.fromisoformat(
                str(form.get("started_at") or "").replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
        db.add(ExamRecord(
            paper_id=paper.id, user_id=target.user_id, score=total, passed=1 if passed else 0,
            answers=user_answers, started_at=started_at,
            submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        if passed:
            prior_pass = db.scalar(select(ExamRecord.id).where(
                ExamRecord.paper_id == paper.id, ExamRecord.user_id == target.user_id,
                ExamRecord.passed == 1).limit(1))
            if prior_pass is None:  # 仅首次通过减风险分，重复通过不叠加
                from decimal import Decimal

                profile = db.get(EmpRiskProfile, target.user_id)
                if profile is None:
                    profile = EmpRiskProfile(user_id=target.user_id)
                    db.add(profile)
                    db.flush()
                profile.total_score = max(profile.total_score - 10, 0)
                profile.training_completion = Decimal("100.00")
                profile.risk_level = _risk_level_of(profile.total_score)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return HTMLResponse(_render_exam_result(paper, total, pct, passed, details, course_id, token))


@app.get("/health")
def health():
    return {"status": "up"}


@app.get("/px/{token}.gif")
def pixel(token: str, request: Request):
    """打开追踪像素：记录 open 事件，返回 1x1 透明 GIF。"""
    from app.modules.tracking.stream import push_event

    push_event(
        token=token, event_type="open",
        ip=request.client.host if request.client else "",
        ua=request.headers.get("user-agent", ""),
    )
    return Response(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
        media_type="image/gif",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/t/{token}")
def redirect(token: str, request: Request):
    """链接点击跳转：记 click 事件 → 302 到演练落地页（带 token 供提交归属）。

    演练域名解析到本服务（与 /px 同驻）；token 无效时兜底 placeholder 页。
    """
    from app.modules.tracking.stream import push_event, resolve_landing_path

    slug, custom_path, _ = resolve_landing_path(token)
    if slug:
        push_event(
            token=token, event_type="click",
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
    # 自定义路径优先（仿真防识别：干净 URL），空则回退默认 /p/{slug}
    location = custom_path or f"/p/{slug or 'placeholder'}"
    if slug:
        location += f"?token={token}"
    return RedirectResponse(location, status_code=302)


@app.get("/px/{token}.png")
def pixel_png(token: str, request: Request):
    """像素降级模式：正常尺寸图片替代 1×1 像素，同样记录 open 事件。"""
    from app.modules.tracking.stream import pixel_png_bytes, push_event

    push_event(
        token=token, event_type="open",
        ip=request.client.host if request.client else "",
        ua=request.headers.get("user-agent", ""),
    )
    return Response(pixel_png_bytes(), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.get("/pa/{token}.png")
def attach_beacon(token: str, request: Request):
    """附件溯源 beacon：docx 内嵌外链图加载时记录 attach_run 事件。

    与 /px（邮件打开像素，记 open）区分——渲染器对附件 beacon 拼 /pa/ 专用
    端点（见 campaign/render.py），使"运行附件"成为独立事件维度（设计文档 4.6）。
    """
    from app.modules.tracking.stream import pixel_png_bytes, push_event

    push_event(
        token=token, event_type="attach_run",
        ip=request.client.host if request.client else "",
        ua=request.headers.get("user-agent", ""),
    )
    return Response(pixel_png_bytes(), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


def _serve_page(page, fields: list[dict] | None, page_path: str,
                request: Request, token: str = ""):
    """落地页渲染共用体：自定义/克隆页渲染 html_content（消毒后），内置类型渲染通用登录卡片。
    带 token 访问即记录 click 事件（点击邮件链接）。"""
    from app.modules.tracking.stream import push_event

    if token:
        push_event(
            token=token, event_type="click",
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
    if page is not None and page.html_content:
        return HTMLResponse(
            # 提交端点跟随受害者在看的 URL：/p/{slug} 或自定义路径，保持一致
            _render_custom_html(page, page.slug, token, str(request.base_url), page_path),
            headers={"Cache-Control": "no-store"},
        )
    title = page.name if page is not None else "统一认证平台"
    if not fields:
        fields = [
            {"field_key": "username", "label": "用户名"},
            {"field_key": "password", "label": "密码", "sensitive_flag": 1},
        ]
    return _render_login_page(title, fields, page_path, token=token)


@app.get("/p/{slug}", response_class=HTMLResponse)
def serve(slug: str, request: Request, token: str = ""):
    """默认路径渲染：/p/{slug}（平台默认形态）。"""
    page, fields = _load_page_and_fields(slug=slug)
    return _serve_page(page, fields, f"/p/{slug}", request, token)


@app.get("/{path:path}", response_class=HTMLResponse)
def serve_custom(path: str, request: Request, token: str = ""):
    """自定义路径兜底（注册在固定路由之后）：path 为空即根路径 /。

    仅当 custom_path 与 /{path} 精确匹配时渲染（仿真防识别：干净 URL）；
    未命中返回 404，演练域名任意路径不渲染仿冒页。
    """
    custom_path = f"/{path}" if path else "/"
    page, fields = _load_page_and_fields(custom_path=custom_path)
    if page is None:
        return Response("Not Found", status_code=404)
    return _serve_page(page, fields, custom_path, request, token)


def _mask_value(value: str) -> str | None:
    """账号类字段脱敏掩码：首字符 + *** + 末字符（邮箱保留域名）。口令类字段不调用本函数。"""
    v = (value or "").strip()
    if not v:
        return None
    if "@" in v:
        local, _, domain = v.partition("@")
        if len(local) <= 2:
            return f"{local[0]}***@{domain}" if local else f"***@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    if len(v) <= 2:
        return f"{v[0]}***"
    return f"{v[0]}***{v[-1]}"


def _fp_hash(fp_json: str) -> str | None:
    """指纹组件 JSON → md5 指纹哈希（fp_hash 列 VARCHAR(32)，与模型设计一致）。"""
    import hashlib

    if not fp_json.strip():
        return None
    try:
        return hashlib.md5(fp_json.encode("utf-8")).hexdigest()
    except Exception:
        return None


async def _submit(request: Request, slug: str):
    """表单捕获：所有字段 AES-GCM 加密入库（明文不落盘）；口令另存长度/首尾字符用于展示；
    账号等非口令字段存脱敏掩码用于展示；指纹组件哈希入库。

    取证：管理端输入操作密码解密全部明文（全程审计）；≤2 位口令只存长度（首尾即完整口令）。

    detail 结构：口令 {len, first?, last?} / 非口令 *_mask（展示）；*_plain {encrypted}（取证）。

    提交后行为按 campaign.training_policy 分支（none 空白页 / popup 教育弹窗 / redirect 302 培训学习页）。
    """
    import base64

    from app.core.security import encrypt_secret
    from app.modules.tracking.stream import push_event

    form = await request.form()
    token = str(form.get("token") or "")
    detail: dict = {}
    for key, value in form.items():
        if key in ("token", "fp"):
            continue
        v = str(value or "")
        if "pass" in key.lower():  # 口令：长度 + 首尾字符（展示），密文走 _plain
            pv = {"len": len(v)}
            if len(v) > 2:
                pv["first"] = v[:1]
                pv["last"] = v[-1:]
            detail[key] = pv
        else:  # 账号等非口令字段：脱敏掩码（展示）
            detail[f"{key}_mask"] = _mask_value(v)
        if v:  # 取证密文：明文 AES-GCM 加密，明文绝不落盘
            try:
                detail[f"{key}_plain"] = {"encrypted": base64.b64encode(encrypt_secret(v)).decode()}
            except Exception:
                pass  # 加密失败退化为不存密文，不阻断提交
    fp_raw = str(form.get("fp") or "")
    fp_hash = _fp_hash(fp_raw)
    if fp_hash:
        detail["fp_hash"] = fp_hash
        try:  # 原始组件（分辨率/GPU/字体/语言/时区等）随事件留存，供设备级查询
            detail["fp"] = json.loads(fp_raw)
        except (json.JSONDecodeError, TypeError):
            pass
    push_event(
        token=token, event_type="submit",
        ip=request.client.host if request.client else "",
        ua=request.headers.get("user-agent", ""),
        detail=detail,
    )
    logger.info("submit captured slug=%s fields=%s fp=%s", slug, list(detail), (fp_hash or "")[:8])
    policy, course_ids, redirect_url = _load_policy(token)
    if policy == "none":
        # 仅记录数据，不做任何提示
        return HTMLResponse(_NONE_PAGE)
    if policy == "url" and redirect_url:
        # 跳转到自定义指定页面（仅允许 http/https，防止 javascript: 等伪协议）
        if redirect_url.startswith(("http://", "https://")):
            return RedirectResponse(redirect_url, status_code=302)
    if policy == "redirect" and course_ids:
        cid = course_ids[0]
        if cid:
            url = f"/learn/{cid}" + (f"?token={quote(token)}" if token else "")
            return RedirectResponse(url, status_code=302)
    return HTMLResponse(_EDU_POPUP)


@app.post("/p/{slug}/submit")
async def submit(slug: str, request: Request):
    """默认路径提交：POST /p/{slug}/submit。"""
    return await _submit(request, slug)


@app.post("/{path:path}")
async def submit_custom(path: str, request: Request):
    """自定义路径提交兜底（注册在固定路由之后）：POST {custom_path}/submit。

    仅匹配已注册的自定义路径（根路径 / 的表单提交到 /submit），未命中返回 404。
    """
    if path != "submit" and not path.endswith("/submit"):
        return Response("Not Found", status_code=404)
    custom_path = "/" + path[: -len("/submit")] if path != "submit" else "/"
    page, _ = _load_page_and_fields(custom_path=custom_path)
    if page is None:
        return Response("Not Found", status_code=404)
    return await _submit(request, page.slug)
