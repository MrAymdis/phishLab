"""AI 服务：SSE 帧协议 {type: token|action|done|error}。

硬约束：AI 产出一律进 ai_draft 草稿态，人工 approve 后入库；审核记录入审计。
LLM Provider 适配层（app.modules.ai.llm）：配置了可用 Provider 时 Copilot/模板/分析
走真实 LLM（用量回填、留审计）；未配置或调用失败时优雅降级本地实现（演示环境保持可用）。
"""
import json
import logging
import re
from datetime import date, datetime

from sqlalchemy import case, func, select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret, encrypt_secret

from .llm import get_client, get_provider, record_usage
from .models import AiDraft, AiMessage, AiProvider, AiSession

logger = logging.getLogger("phishlab.ai")

_SCENE_CN = {
    "finance": "财务报销", "hr": "HR通知", "system": "系统升级",
    "lottery": "中奖通知", "holiday": "节假日", "alert": "安全告警", "security": "安全告警",
}

_DEFAULT_SYSTEM_PROMPT = (
    "你是 PhishLab 企业网络安全钓鱼演练平台的 AI 助手，服务于安全运营人员。"
    "回答使用中文，简洁专业；涉及平台数据的回答基于用户可见数据，不编造演练结果；"
    "AI 产出的模板/文案属于草稿，需人工确认后生效。"
)


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
    """Copilot 对话：返回 async generator 供 SSE。

    有可用 Provider → LLM 流式（历史上下文 + 用量回填 + 失败 error 帧）；
    未配置 Provider → 降级本地回复引擎（演示环境可用性兜底）。
    """
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
    db.commit()

    provider = get_provider(db)
    if provider is None:
        # 降级：本地回复引擎（未配置 LLM Provider 时保持可用）
        reply = _local_reply(db, message)
        db.add(AiMessage(session_id=session.id, role="assistant", content=reply))
        db.commit()

        async def local_gen():
            for chunk in re.split(r"(?<=。)|(?<=\n)", reply):
                if chunk:
                    yield {"data": json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)}
            yield {"data": json.dumps({"type": "done", "content": str(session.id)})}

        return local_gen()

    # LLM 路径：最近 20 条历史作为上下文（含本轮 user 消息）
    history = db.scalars(
        select(AiMessage).where(AiMessage.session_id == session.id)
        .order_by(AiMessage.id.desc()).limit(20)
    ).all()
    messages = [
        {"role": m.role, "content": (m.content or "")[:2000]}
        for m in reversed(history) if m.role in ("user", "assistant")
    ]
    system_prompt = provider.system_prompt or _DEFAULT_SYSTEM_PROMPT
    client = get_client(db, provider)

    async def llm_gen():
        full = ""
        tokens_in = tokens_out = None
        try:
            async for frame in client.stream(
                messages, system_prompt=system_prompt,
                temperature=float(provider.temperature or 0.7),
                max_tokens=provider.max_tokens or 2048,
            ):
                if frame["type"] == "token":
                    full += frame["content"]
                    yield {"data": json.dumps(
                        {"type": "token", "content": frame["content"]}, ensure_ascii=False)}
                elif frame["type"] == "usage":
                    tokens_in, tokens_out = frame.get("tokens_in"), frame.get("tokens_out")
            if not full.strip():
                raise BizError(ErrorCode.AI_PROVIDER_ERROR, "LLM 返回为空，请重试")
            db.add(AiMessage(session_id=session.id, role="assistant", content=full,
                             tokens_in=tokens_in, tokens_out=tokens_out))
            record_usage(db, provider, tokens_in, tokens_out)
            yield {"data": json.dumps({"type": "done", "content": str(session.id)})}
        except BizError as exc:
            logger.warning("llm stream biz error: %s", exc.message)
            yield {"data": json.dumps({"type": "error", "content": exc.message}, ensure_ascii=False)}
        except Exception:
            logger.exception("llm stream failed provider=%s", provider.id)
            yield {"data": json.dumps({"type": "error", "content": "AI 服务暂时不可用，请稍后重试"})}

    return llm_gen()


def _extract_json_meta(text: str) -> dict | None:
    """从 LLM 输出提取 JSON：直接解析 / ```json 代码块 / 首对花括号。失败返回 None。"""
    for candidate in (text.strip(),):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return None


_TEMPLATE_SYSTEM = (
    "你是 PhishLab 钓鱼演练平台的邮件模板创作专家。根据用户要求生成一条演练邮件模板。"
    "只输出一个 JSON 对象，不要输出任何其他文字。JSON 字段："
    '{"name": 模板名, "subject": 邮件主题, "body": HTML 正文（可含 {{.FirstName}}/{{.ResetURL}} '
    '变量占位符，样式用内联 style）, "sender": 伪装发件人显示名, "difficulty": 1-3}。'
    "正文要可信、符合中文企业邮件习惯，不包含真实恶意内容。"
)


async def generate_template(db, account, payload: dict) -> int:
    """AI 模板生成 → ai_draft(biz_type=email_template)。

    LLM 可用时由 LLM 产出 JSON 草稿；未配置/调用失败/输出非法时降级本地模板。
    """
    scene = payload.get("scene", "finance")
    scene_cn = _SCENE_CN.get(scene, scene)
    audience = payload.get("audience") or "全体员工"
    tone = payload.get("tone") or "正式"
    difficulty = payload.get("difficulty", 2)

    meta = None
    fallback_reason = None
    provider = get_provider(db)
    if provider is not None:
        try:
            client = get_client(db, provider)
            result = await client.chat(
                [{"role": "user", "content":
                  f"场景：{scene_cn}；目标人群：{audience}；语气：{tone}；难度 {difficulty}。"
                  f"生成一条演练邮件模板。"}],
                system_prompt=provider.system_prompt or _TEMPLATE_SYSTEM,
                temperature=float(provider.temperature or 0.7),
                max_tokens=provider.max_tokens or 2048,
            )
            raw = _extract_json_meta(result["content"])
            if raw and raw.get("subject") and raw.get("body"):
                meta = {
                    "name": str(raw.get("name") or f"{scene_cn}·AI生成模板")[:64],
                    "scene": scene, "subject": str(raw["subject"])[:200],
                    "body": str(raw["body"]), "sender": str(raw.get("sender") or "信息安全部")[:64],
                    "difficulty": int(raw.get("difficulty") or difficulty),
                    "tone": tone, "audience": audience,
                }
                record_usage(db, provider, result.get("tokens_in"), result.get("tokens_out"))
            else:
                fallback_reason = "LLM 输出非预期 JSON，降级本地模板"
        except BizError as exc:
            fallback_reason = f"LLM 调用失败降级：{exc.message}"
        except Exception:
            logger.exception("generate_template llm failed")
            fallback_reason = "LLM 调用异常降级"

    if meta is None:
        subject = f"【{scene_cn}通知】请尽快处理您的待办事项"
        body = (
            f"<div style='font-family:sans-serif;line-height:1.8'>"
            f"<p>{{{{.FirstName}}}}，您好：</p>"
            f"<p>{scene_cn}相关事项需要您确认，请于今日 18:00 前点击下方链接完成操作。</p>"
            f"<p><a href='{{{{.ResetURL}}}}'>立即处理 →</a></p>"
            f"<p style='color:#888'>本邮件由系统自动发送（{tone}语气 · 目标人群：{audience}）</p></div>"
        )
        meta = {
            "name": f"{scene_cn}·AI生成模板", "scene": scene, "subject": subject,
            "body": body, "sender": "信息安全部", "difficulty": difficulty,
            "tone": tone, "audience": audience,
        }
    draft = AiDraft(
        biz_type="email_template",
        title=meta["subject"],
        content=json.dumps(meta, ensure_ascii=False),
        status="draft",
        created_by=account.id,
    )
    db.add(draft)
    db.commit()
    record_audit(db, account=account, module="ai", action="generate_template",
                 target_type="ai_draft", target_id=str(draft.id),
                 detail={"llm": provider is not None, "fallback": fallback_reason})
    return draft.id


_ANALYSIS_SYSTEM = (
    "你是 PhishLab 安全演练平台的安全分析师。根据提供的平台真实指标数据撰写分析报告。"
    "只输出 Markdown 格式报告，包含：执行摘要、关键发现、改进建议。中文输出。"
)


async def generate_analysis(db, account, kind: str, target: dict) -> int:
    """智能分析报告（演练效果/部门画像/趋势预测/培训建议）→ ai_draft。

    LLM 可用时基于平台真实指标由 LLM 撰写；未配置/失败时降级本地生成。
    """
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

    content = None
    fallback_reason = None
    provider = get_provider(db)
    if provider is not None:
        metrics = (f"累计演练 {campaign_cnt} 场，覆盖 {total_target:,} 人次，"
                   f"平均中招率 {rate:.1f}%")
        try:
            client = get_client(db, provider)
            result = await client.chat(
                [{"role": "user", "content":
                  f"请撰写「{kind_cn}」报告。平台真实指标：{metrics}。"
                  f"目标参数：{json.dumps(target, ensure_ascii=False)}"}],
                system_prompt=provider.system_prompt or _ANALYSIS_SYSTEM,
                temperature=float(provider.temperature or 0.7),
                max_tokens=provider.max_tokens or 2048,
            )
            if result["content"].strip():
                content = result["content"]
                record_usage(db, provider, result.get("tokens_in"), result.get("tokens_out"))
            else:
                fallback_reason = "LLM 输出为空，降级本地生成"
        except BizError as exc:
            fallback_reason = f"LLM 调用失败降级：{exc.message}"
        except Exception:
            logger.exception("generate_analysis llm failed")
            fallback_reason = "LLM 调用异常降级"

    if content is None:
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
                 target_type="ai_draft", target_id=str(draft.id),
                 detail={"kind": kind, "llm": provider is not None, "fallback": fallback_reason})
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


# ---------- LLM Provider 管理（红线 2：Key 加密入库、API 只回显掩码） ----------

PROVIDER_TYPES = ("openai", "claude", "wenxin", "tongyi", "local")


def _mask_key(enc: bytes | None) -> str:
    """API Key 掩码回显：sk-****abcd（≤8 位全掩码；解密失败统一 ***）。"""
    if not enc:
        return ""
    try:
        key = decrypt_secret(enc)
    except Exception:
        return "***"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]


def _provider_usage(db, provider_ids: list[int]) -> dict[int, dict]:
    """最近 7 天用量聚合（provider_id → {calls, tokens_in, tokens_out}）。"""
    from datetime import timedelta

    from sqlalchemy import func as sa_func

    from .models import AiUsageStat

    if not provider_ids:
        return {}
    rows = db.execute(
        select(AiUsageStat.provider_id,
               sa_func.coalesce(sa_func.sum(AiUsageStat.call_count), 0),
               sa_func.coalesce(sa_func.sum(AiUsageStat.tokens_in), 0),
               sa_func.coalesce(sa_func.sum(AiUsageStat.tokens_out), 0))
        .where(AiUsageStat.provider_id.in_(provider_ids),
               AiUsageStat.stat_date >= (date.today() - timedelta(days=6)))
        .group_by(AiUsageStat.provider_id)
    ).all()
    return {pid: {"calls": int(c), "tokens_in": int(ti), "tokens_out": int(to)}
            for pid, c, ti, to in rows}


def list_providers(db) -> list[dict]:
    rows = db.scalars(select(AiProvider).order_by(AiProvider.id)).all()
    usage = _provider_usage(db, [p.id for p in rows])
    return [
        {
            "id": p.id, "name": p.name, "type": p.type, "endpoint": p.endpoint,
            "model": p.model, "api_key_masked": _mask_key(p.api_key_enc),
            "temperature": float(p.temperature or 0.7), "max_tokens": p.max_tokens or 2048,
            "system_prompt": p.system_prompt, "enabled": p.enabled == 1,
            "data_outbound": p.data_outbound == 1,
            "usage_7d": usage.get(p.id, {"calls": 0, "tokens_in": 0, "tokens_out": 0}),
        }
        for p in rows
    ]


def _check_provider_payload(payload: dict) -> None:
    ptype = payload.get("type")
    if ptype not in PROVIDER_TYPES:
        raise BizError(ErrorCode.PARAM_INVALID, f"type 仅支持 {PROVIDER_TYPES}")
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 64:
        raise BizError(ErrorCode.PARAM_INVALID, "name 必填且 ≤64 字")
    endpoint = payload.get("endpoint") or ""
    if endpoint and not endpoint.startswith(("http://", "https://")):
        raise BizError(ErrorCode.PARAM_INVALID, "endpoint 需为 http(s):// 地址")
    temp = float(payload.get("temperature", 0.7))
    if not 0 <= temp <= 2:
        raise BizError(ErrorCode.PARAM_INVALID, "temperature 需在 0-2 之间")
    mt = int(payload.get("max_tokens", 2048))
    if not 1 <= mt <= 16384:
        raise BizError(ErrorCode.PARAM_INVALID, "max_tokens 需在 1-16384 之间")


def create_provider(db, account, payload: dict) -> dict:
    _check_provider_payload(payload)
    key = (payload.get("api_key") or "").strip()
    if not key and payload.get("type") != "local":
        raise BizError(ErrorCode.PARAM_INVALID, "api_key 必填（local 类型可留空）")
    p = AiProvider(
        name=payload["name"].strip(),
        type=payload["type"],
        endpoint=(payload.get("endpoint") or "").strip() or None,
        api_key_enc=encrypt_secret(key) if key else None,
        model=(payload.get("model") or "").strip() or None,
        temperature=payload.get("temperature", 0.7),
        max_tokens=payload.get("max_tokens", 2048),
        system_prompt=(payload.get("system_prompt") or "").strip() or None,
        enabled=1 if payload.get("enabled", True) else 0,
        data_outbound=1 if payload.get("data_outbound", True) else 0,
    )
    db.add(p)
    db.commit()
    record_audit(db, account=account, module="ai", action="provider_create",
                 target_type="ai_provider", target_id=str(p.id),
                 detail={"name": p.name, "type": p.type})
    return {"id": p.id, "api_key_masked": _mask_key(p.api_key_enc)}


def update_provider(db, account, provider_id: int, payload: dict) -> dict:
    p = db.get(AiProvider, provider_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "Provider 不存在")
    _check_provider_payload(payload)
    for field in ("name", "type", "endpoint", "model", "system_prompt"):
        if field in payload:
            setattr(p, field, (payload[field] or "").strip() or None)
    if "temperature" in payload:
        p.temperature = payload["temperature"]
    if "max_tokens" in payload:
        p.max_tokens = payload["max_tokens"]
    if "enabled" in payload:
        p.enabled = 1 if payload["enabled"] else 0
    if "data_outbound" in payload:
        p.data_outbound = 1 if payload["data_outbound"] else 0
    key = (payload.get("api_key") or "").strip()
    if key:
        p.api_key_enc = encrypt_secret(key)  # 更新 Key：旧密文覆盖，审计留痕
        record_audit(db, account=account, module="ai", action="provider_key_rotate",
                     target_type="ai_provider", target_id=str(provider_id),
                     detail={"name": p.name})
    db.commit()
    record_audit(db, account=account, module="ai", action="provider_update",
                 target_type="ai_provider", target_id=str(provider_id),
                 detail={"name": p.name, "type": p.type})
    return {"id": p.id, "api_key_masked": _mask_key(p.api_key_enc)}


def delete_provider(db, account, provider_id: int) -> None:
    p = db.get(AiProvider, provider_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "Provider 不存在")
    db.delete(p)
    db.commit()
    record_audit(db, account=account, module="ai", action="provider_delete",
                 target_type="ai_provider", target_id=str(provider_id),
                 detail={"name": p.name})


async def test_provider(db, provider_id: int) -> dict:
    """连通性测试：最小 chat 请求（16 token 上限），返回延迟与回复摘要。"""
    import time

    from .llm import get_client

    p = db.get(AiProvider, provider_id)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "Provider 不存在")
    client = get_client(db, p)
    started = time.monotonic()
    result = await client.chat([{"role": "user", "content": "回复 OK 即可"}],
                               system_prompt=p.system_prompt or "你是连通性测试助手，只回复 OK",
                               temperature=0.0, max_tokens=16)
    elapsed = round(time.monotonic() - started, 2)
    return {"ok": True, "latency_ms": int(elapsed * 1000),
            "reply": (result.get("content") or "")[:120],
            "tokens_in": result.get("tokens_in"), "tokens_out": result.get("tokens_out")}
