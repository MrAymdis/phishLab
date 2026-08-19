"""落地页服务（独立演练域名部署）：仿冒页托管、表单捕获、教育弹窗、培训跳转。

红线：口令类字段永不存明文——只记录字段名与输入长度。
演示模式：绑定 8082 端口，开发机 hosts 映射演练域名后即可完整演示
（点击邮件链接 → 仿冒登录页 → 提交 → 教育弹窗）。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phishlab.landing")

app = FastAPI(title="PhishLab Landing", docs_url=None)

_EDU_POPUP = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>安全演练提示</title></head>
<body style="font-family:sans-serif;display:flex;justify-content:center;padding-top:80px">
<div style="max-width:520px;border:1px solid #d1d5db;border-radius:12px;padding:32px">
<h2 style="color:#D85A30">⚠️ 这是一次钓鱼演练</h2>
<p>您刚才差点泄露了密码！请放心，本次为内部安全演练，您输入的内容<b>不会被记录</b>。</p>
<p>请记住三点：核对发件人域名、不点击可疑链接、可疑邮件及时举报。</p>
</div></body></html>"""


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


def _render_custom_html(page, slug: str, token: str) -> str:
    """渲染自定义/克隆页面：静态渲染 + 消毒 + 表单重定向 + token/指纹注入，
    逻辑收敛在 template.service.render_cloned_html（预览接口共用，保证一致）。"""
    from app.modules.template.service import render_cloned_html

    return render_cloned_html(page.html_content or "", slug, token, page.clone_from_url or "")


def _load_page(slug: str):
    """slug → LandingPage；独立部署下与主库同库。TODO(三期)：接入 Redis 缓存。"""
    from app.db.session import SessionLocal
    from app.modules.template.models import LandingPage

    db = SessionLocal()
    try:
        return db.query(LandingPage).filter(LandingPage.slug == slug).first()
    finally:
        db.close()


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
            _render_custom_html(page, slug, token),
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
    """表单捕获：口令字段只存长度（红线）；账号存脱敏掩码；指纹组件哈希入库。

    TODO(一期)：token 反查 campaign → training_policy：redirect(302 培训页)/popup/none
    """
    from app.modules.tracking.stream import push_event

    form = await request.form()
    token = str(form.get("token") or "")
    detail: dict = {}
    for key, value in form.items():
        if key in ("token", "fp"):
            continue
        v = str(value or "")
        if "pass" in key.lower():  # 口令：只记长度，绝不存明文/掩码
            detail[key] = {"len": len(v)}
        else:  # 账号等非口令字段：脱敏掩码
            detail[f"{key}_mask"] = _mask_value(v)
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
    return HTMLResponse(_EDU_POPUP)
