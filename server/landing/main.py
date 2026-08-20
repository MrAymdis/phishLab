"""落地页服务（独立演练域名部署）：仿冒页托管、表单捕获、教育弹窗、培训跳转。

红线：口令类字段永不存明文——只记录字段名与输入长度。
演示模式：绑定 8082 端口，开发机 hosts 映射演练域名后即可完整演示
（点击邮件链接 → 仿冒登录页 → 提交 → 按 training_policy 处理）。

提交后行为按演练 training_policy 分支：
  none     → 空白页（仅记录数据，不告知中招）
  popup    → 教育弹窗（可关闭）
  redirect → 302 培训学习页 /learn/{course_id}
"""
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


def _render_login_page(title: str, fields: list[dict], slug: str, token: str = "") -> str:
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
  <form method="post" action="/p/{slug}/submit" id="login-form" style="display:flex;flex-direction:column">
    {fields_html}
    <input type="hidden" name="token" value="{token}" />
    <input type="hidden" name="fp" id="fp-input" value="" />
    <button type="submit" style="margin-top:12px;padding:10px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer">登 录</button>
  </form>
  <p style="text-align:center;color:#aaa;font-size:11px;margin-top:16px">© 企业信息安全中心 · 内部系统</p>
</div>
</body></html>""" + FP_SCRIPT


def _render_custom_html(page, slug: str, token: str, submit_base: str = "") -> str:
    """渲染自定义/克隆页面：静态渲染 + 消毒 + 表单重定向 + token/指纹注入，
    逻辑收敛在 template.service.render_cloned_html（预览接口共用，保证一致）。

    submit_base 传演练域名（request.base_url）：克隆页 <base> 指向原站，表单 action
    必须用绝对 URL，否则会被 base 劫持提交到原站域名。"""
    from app.modules.template.service import render_cloned_html

    return render_cloned_html(
        page.html_content or "", slug, token, page.clone_from_url or "", submit_base
    )


def _load_page(slug: str):
    """slug → LandingPage；独立部署下与主库同库。TODO(三期)：接入 Redis 缓存。"""
    from app.db.session import SessionLocal
    from app.modules.template.models import LandingPage

    db = SessionLocal()
    try:
        return db.query(LandingPage).filter(LandingPage.slug == slug).first()
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


@app.get("/learn/{course_id}", response_class=HTMLResponse)
def learn(course_id: int):
    """员工端培训学习页（redirect 模式 302 落点）。TODO(三期)：接入真实课件。"""
    from app.db.session import SessionLocal
    from app.modules.training.models import Course

    title = "安全培训课程"
    desc = ""
    db = SessionLocal()
    try:
        c = db.get(Course, course_id)
        if c is not None:
            title = c.title
            desc = c.description or f"课件形态：{c.material or c.type} · 时长 {c.duration_min} 分钟"
    finally:
        db.close()
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;background:#f5f7fa;font-family:'Microsoft YaHei',sans-serif;display:flex;justify-content:center;padding-top:80px">
<div style="max-width:520px;background:#fff;border-radius:12px;padding:32px;text-align:center">
<h2 style="color:#1D9E75;margin:0 0 8px">✅ 您已进入安全培训</h2>
<p style="color:#555;margin:0 0 20px">{title}</p>
<p style="color:#999;font-size:12px;line-height:1.7">{desc or "培训课件接入中，敬请期待。"}</p>
</div></body></html>""")


def _load_page_fields(slug: str, page=None) -> tuple[str, list[dict]]:
    """slug → (页面名, 表单字段)。TODO(三期)：接入 Redis 缓存。"""
    from app.db.session import SessionLocal
    from app.modules.template.models import LandingFormField

    if page is None:
        page = _load_page(slug)
    if page is None:
        return "统一认证平台", [
            {"field_key": "username", "label": "用户名"},
            {"field_key": "password", "label": "密码", "sensitive_flag": 1},
        ]
    db = SessionLocal()
    try:
        fields = [
            {"field_key": f.field_key, "label": f.label or f.field_key,
             "sensitive_flag": f.sensitive_flag}
            for f in db.query(LandingFormField)
            .filter(LandingFormField.page_id == page.id)
            .order_by(LandingFormField.sort).all()
        ]
    finally:
        db.close()
    if not fields:
        fields = [
            {"field_key": "username", "label": "用户名"},
            {"field_key": "password", "label": "密码", "sensitive_flag": 1},
        ]
    return page.name, fields


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


@app.get("/p/{slug}", response_class=HTMLResponse)
def serve(slug: str, request: Request, token: str = ""):
    """渲染落地页：自定义/克隆页面渲染 html_content（消毒后），内置类型渲染通用登录卡片。
    带 token 访问即记录 click 事件（点击邮件链接）。"""
    from app.modules.tracking.stream import push_event

    if token:
        push_event(
            token=token, event_type="click",
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
    page = _load_page(slug)
    if page is not None and page.html_content:
        return HTMLResponse(
            _render_custom_html(page, slug, token, str(request.base_url)),
            headers={"Cache-Control": "no-store"},
        )
    # TODO(一期)：注入指纹采集 JS（Canvas/WebGL/字体），写入 fingerprint 表
    title, fields = _load_page_fields(slug, page)
    return _render_login_page(title, fields, slug, token=token)


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


@app.post("/p/{slug}/submit")
async def submit(slug: str, request: Request):
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
    fp_hash = _fp_hash(str(form.get("fp") or ""))
    if fp_hash:
        detail["fp_hash"] = fp_hash
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
