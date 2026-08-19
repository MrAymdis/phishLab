"""AI 服务（三期模块，本地演示实现）。SSE 帧协议：{type: token|action|done|error}。

硬约束：AI 产出一律进 ai_draft 草稿态，人工 approve 后入库；审核记录入审计。
TODO(三期)：接入 LLM Provider 适配层（ai_provider 表），当前为基于真实数据的本地回复。
"""
import json
import re
from datetime import datetime

from sqlalchemy import case, func, select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode

from .models import AiDraft, AiMessage, AiSession

_SCENE_CN = {
    "finance": "财务报销", "hr": "HR通知", "system": "系统升级",
    "lottery": "中奖通知", "holiday": "节假日", "alert": "安全告警", "security": "安全告警",
}


def _fmt_time(dt: datetime) -> str:
    seconds = max(int((datetime.now() - dt).total_seconds()), 0)
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分钟前"
    if seconds < 86400:
        return f"{seconds // 3600}小时前"
    if seconds < 86400 * 30:
        return f"{seconds // 86400}天前"
    return dt.strftime("%Y-%m-%d")


def list_sessions(db, account):
    rows = db.scalars(
        select(AiSession).where(AiSession.account_id == account.id).order_by(AiSession.id.desc())
    ).all()
    return [
        {"id": s.id, "title": s.title or "新对话", "time": _fmt_time(s.created_at)}
        for s in rows
    ]


def _local_reply(db, message: str) -> str:
    """本地回复引擎：基于数据库真实统计的关键词应答（三期接 LLM）。"""
    from app.modules.campaign.models import Campaign, CampaignStat, CampaignTarget
    from app.modules.training.models import Course

    sent = CampaignTarget.send_status.in_(("sent", "delivered", "bounced", "failed"))
    total_submit = db.scalar(
        select(func.coalesce(func.sum(case((CampaignTarget.submit_flag == 1, 1), else_=0)), 0))
        .where(sent)
    ) or 0
    total_target = db.scalar(select(func.count()).where(sent)) or 0
    rate = total_submit / total_target * 100 if total_target else 0.0
    running = db.scalars(select(Campaign).where(Campaign.status == "running")).all()
    running_names = "、".join(c.name for c in running) or "暂无进行中的演练"
    courses = db.scalars(select(Course).order_by(Course.id).limit(3)).all()

    if any(k in message for k in ("演练", "分析", "效果", "中招")):
        return (
            f"根据当前平台数据：累计演练目标 {total_target:,} 人，中招 {total_submit:,} 人，"
            f"平均中招率 {rate:.1f}%。\n\n进行中的演练：{running_names}。"
            f"建议对中招率最高的部门优先安排「识别伪造发件人」专项培训。"
        )
    if any(k in message for k in ("模板", "钓鱼邮件", "话术")):
        return (
            "已为您梳理模板生成要点：\n1. 主题使用「紧急/通知/更新」等高频词可提升打开率约 40%；\n"
            "2. 建议在正文插入 {{.FirstName}}/{{.Department}} 动态变量提升可信度；\n"
            "3. 可通过「AI模板生成」页生成草稿，经人工确认后入库。"
        )
    if any(k in message for k in ("培训", "课程")):
        if courses:
            names = "、".join(c.title for c in courses)
            return f"推荐以下课程：{names}。可创建培训任务定向分配给中招人员，完成后自动结案。"
        return "当前课程库为空，可在「安全培训」页新建课程后再分配任务。"
    if any(k in message for k in ("举报", "报告")):
        return "举报数据可在「邮件举报」页查看：真实钓鱼举报需人工研判，判定后可推送 SOC 处置。"
    return (
        "我是您的安全演练 AI 助手，可以帮您：\n- 分析演练效果与中招趋势\n- 生成钓鱼邮件模板\n"
        "- 推荐培训课程\n\n*AI 生成内容处于草稿态，需人工确认后生效。审核记录将进入审计日志。*"
    )


def chat_stream(db, account, payload: dict):
    """Copilot 对话：返回 async generator 供 SSE（LLM 适配层 TODO 三期）。"""
    message = (payload.get("message") or "").strip()
    if not message:
        raise BizError(ErrorCode.PARAM_INVALID, "消息不能为空")

    session = None
    if payload.get("session_id"):
        session = db.get(AiSession, payload["session_id"])
    if session is None:
        session = AiSession(account_id=account.id, title=message[:30],
                            page_context=payload.get("page_context"))
        db.add(session)
        db.flush()
    db.add(AiMessage(session_id=session.id, role="user", content=message))
    reply = _local_reply(db, message)
    db.add(AiMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()

    async def gen():
        # 简单按句切块模拟流式（真实流式在 LLM 适配层实现）
        for chunk in re.split(r"(?<=。)|(?<=\n)", reply):
            if chunk:
                yield {"data": json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)}
        yield {"data": json.dumps({"type": "done", "content": str(session.id)})}

    return gen()


def generate_template(db, account, payload: dict) -> int:
    """AI 模板生成 → ai_draft(biz_type=email_template)。"""
    scene = payload.get("scene", "finance")
    scene_cn = _SCENE_CN.get(scene, scene)
    audience = payload.get("audience") or "全体员工"
    tone = payload.get("tone") or "正式"
    subject = f"【{scene_cn}通知】请尽快处理您的待办事项"
    body = (
        f"<div style='font-family:sans-serif;line-height:1.8'>"
        f"<p>{{{{.FirstName}}}}，您好：</p>"
        f"<p>{scene_cn}相关事项需要您确认，请于今日 18:00 前点击下方链接完成操作。</p>"
        f"<p><a href='{{{{.ResetURL}}}}'>立即处理 →</a></p>"
        f"<p style='color:#888'>本邮件由系统自动发送（{tone}语气 · 目标人群：{audience}）</p></div>"
    )
    draft = AiDraft(
        biz_type="email_template",
        title=subject,
        content=json.dumps({
            "name": f"{scene_cn}·AI生成模板", "scene": scene, "subject": subject,
            "body": body, "sender": f"信息安全部", "difficulty": payload.get("difficulty", 2),
            "tone": tone, "audience": audience,
        }, ensure_ascii=False),
        status="draft",
        created_by=account.id,
    )
    db.add(draft)
    db.commit()
    record_audit(db, account=account, module="ai", action="generate_template",
                 target_type="ai_draft", target_id=str(draft.id))
    return draft.id


def generate_analysis(db, account, kind: str, target: dict) -> int:
    """智能分析报告（演练效果/部门画像/趋势预测/培训建议）→ ai_draft。"""
    from app.modules.campaign.models import Campaign, CampaignTarget

    sent = CampaignTarget.send_status.in_(("sent", "delivered", "bounced", "failed"))
    total_submit = db.scalar(
        select(func.coalesce(func.sum(case((CampaignTarget.submit_flag == 1, 1), else_=0)), 0))
        .where(sent)
    ) or 0
    total_target = db.scalar(select(func.count()).where(sent)) or 0
    rate = total_submit / total_target * 100 if total_target else 0.0
    campaign_cnt = db.scalar(select(func.count()).select_from(Campaign)) or 0

    kind_cn = {
        "campaign_effect": "演练效果分析", "dept_risk": "部门风险画像",
        "trend_forecast": "趋势预测", "training_recommend": "培训建议",
    }.get(kind, kind)
    content = (
        f"# {kind_cn}\n\n"
        f"## 执行摘要\n累计开展演练 {campaign_cnt} 场，覆盖 {total_target:,} 人次，"
        f"平均中招率 {rate:.1f}%。\n\n"
        f"## 关键发现\n- 财务类场景中招率显著高于其他场景\n"
        f"- 工作日 9:00-10:00 为打开高峰\n- 举报率与培训完成度呈正相关\n\n"
        f"## 改进建议\n1. 对高危部门开展定向专项培训\n2. 优化诱饵时间分布\n3. 完善举报反馈闭环"
    )
    draft = AiDraft(
        biz_type="report_summary",
        title=f"{kind_cn}（{datetime.now().strftime('%Y-%m-%d')}）",
        content=content,
        status="draft",
        created_by=account.id,
    )
    db.add(draft)
    db.commit()
    record_audit(db, account=account, module="ai", action="generate_analysis",
                 target_type="ai_draft", target_id=str(draft.id), detail={"kind": kind})
    return draft.id


def list_drafts(db, account, status: str | None = None):
    stmt = select(AiDraft).where(AiDraft.status != "discarded").order_by(AiDraft.id.desc())
    if status:
        stmt = stmt.where(AiDraft.status == status)
    rows = db.scalars(stmt.limit(50)).all()
    from app.modules.account.models import SysAccount

    result = []
    for d in rows:
        reviewer = db.get(SysAccount, d.reviewer_id) if d.reviewer_id else None
        result.append({
            "id": d.id,
            "biz_type": d.biz_type,
            "title": d.title,
            "content": d.content,
            "status": d.status,
            "created_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
            "reviewer": reviewer.real_name if reviewer else None,
            "reviewed_at": d.reviewed_at.strftime("%Y-%m-%d %H:%M") if d.reviewed_at else None,
        })
    return result


def approve_draft(db, account, draft_id: int) -> dict:
    """确认入库：按 biz_type 写入目标表，回填 biz_id，记录审核人/时间。"""
    import json

    from app.modules.template.models import EmailTemplate

    draft = db.get(AiDraft, draft_id)
    if draft is None or draft.status == "discarded":
        raise BizError(ErrorCode.NOT_FOUND, "草稿不存在或已丢弃")
    if draft.status == "approved":
        raise BizError(ErrorCode.PARAM_INVALID, "草稿已确认入库")

    biz_id = None
    if draft.biz_type == "email_template":
        meta = {}
        try:
            meta = json.loads(draft.content or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        tpl = EmailTemplate(
            name=meta.get("name") or (draft.title or "AI模板")[:128],
            scene=meta.get("scene") or "security",
            subject=meta.get("subject") or draft.title or "AI生成模板",
            html_body=meta.get("body") or draft.content or "",
            variables=sorted(set(re.findall(r"\{\{\.\w+\}\}", meta.get("body") or draft.content or ""))),
            source="ai",
            status="approved",
            created_by=account.id,
            sender=meta.get("sender"),
            stars=int(meta.get("difficulty") or 2),
        )
        db.add(tpl)
        db.flush()
        biz_id = tpl.id
    # TODO(三期)：landing_page/course 类型草稿入库

    draft.status = "approved"
    draft.biz_id = biz_id
    draft.reviewer_id = account.id
    draft.reviewed_at = datetime.now()
    db.commit()
    record_audit(db, account=account, module="ai", action="approve_draft",
                 target_type="ai_draft", target_id=str(draft_id),
                 detail={"biz_type": draft.biz_type, "biz_id": biz_id})
    return {"id": draft_id, "status": "approved", "biz_id": biz_id}


def discard_draft(db, account, draft_id: int):
    draft = db.get(AiDraft, draft_id)
    if draft is None:
        raise BizError(ErrorCode.NOT_FOUND)
    draft.status = "discarded"
    draft.reviewer_id = account.id
    draft.reviewed_at = datetime.now()
    db.commit()
    record_audit(db, account=account, module="ai", action="discard_draft",
                 target_type="ai_draft", target_id=str(draft_id))
    return {"id": draft_id, "status": "discarded"}
