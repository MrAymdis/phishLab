"""落地页服务（独立演练域名部署）：仿冒页托管、表单捕获、教育弹窗、培训跳转。

红线：口令类字段永不存明文——只记录字段名与输入长度。
演示模式：绑定 8082 端口，开发机 hosts 映射演练域名后即可完整演示
（点击邮件链接 → 仿冒登录页 → 提交 → 教育弹窗）。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

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


def _render_login_page(title: str, fields: list[dict], token: str = "") -> str:
    """渲染仿冒登录页：标题 + 表单字段（口径类字段标注不落库说明仅在演练端）。"""
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
  <form method="post" action="submit" style="display:flex;flex-direction:column">
    {fields_html}
    <input type="hidden" name="token" value="{token}" />
    <button type="submit" style="margin-top:12px;padding:10px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer">登 录</button>
  </form>
  <p style="text-align:center;color:#aaa;font-size:11px;margin-top:16px">© 企业信息安全中心 · 内部系统</p>
</div>
</body></html>"""


def _load_page_fields(slug: str) -> tuple[str, list[dict]]:
    """slug → (页面名, 表单字段)。TODO(三期)：接入 Redis 缓存。"""
    from app.db.session import SessionLocal
    from app.modules.template.models import LandingFormField, LandingPage

    db = SessionLocal()
    try:
        page = db.query(LandingPage).filter(LandingPage.slug == slug).first()
        if page is None:
            return "统一认证平台", [
                {"field_key": "username", "label": "用户名"},
                {"field_key": "password", "label": "密码", "sensitive_flag": 1},
            ]
        fields = [
            {"field_key": f.field_key, "label": f.label or f.field_key,
             "sensitive_flag": f.sensitive_flag}
            for f in db.query(LandingFormField)
            .filter(LandingFormField.page_id == page.id)
            .order_by(LandingFormField.sort).all()
        ]
        if not fields:
            fields = [
                {"field_key": "username", "label": "用户名"},
                {"field_key": "password", "label": "密码", "sensitive_flag": 1},
            ]
        return page.name, fields
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "up"}


@app.get("/p/{slug}", response_class=HTMLResponse)
def serve(slug: str, token: str = ""):
    """渲染仿冒登录页（字段来自落地页素材库；追踪 token 随表单提交回传）。"""
    title, fields = _load_page_fields(slug)
    # TODO(一期)：注入指纹采集 JS（Canvas/WebGL/字体），写入 fingerprint 表
    return _render_login_page(title, fields, token=token)


@app.post("/p/{slug}/submit")
async def submit(slug: str, request: Request):
    """表单捕获：敏感字段只存 字段名+长度，随后按演练培训策略跳转/弹窗。

    TODO(一期)：
    - token 反查 campaign → training_policy：redirect(302 培训页)/popup/none
    - SUBMIT 事件写 evt:stream（含脱敏 detail）→ 触发高危预警判定
    """
    form = await request.form()
    masked = {
        key: {"len": len(value or "")} if "pass" in key.lower() else {"present": True}
        for key, value in form.items()
    }
    logger.info("submit captured slug=%s fields=%s", slug, list(masked))
    return HTMLResponse(_EDU_POPUP)
