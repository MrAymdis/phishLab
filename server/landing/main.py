"""落地页服务（独立演练域名部署）：仿冒页托管、表单捕获、教育弹窗、培训跳转。

红线：口令类字段永不存明文——只记录字段名与输入长度。
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


@app.get("/health")
def health():
    return {"status": "up"}


@app.get("/p/{slug}", response_class=HTMLResponse)
def serve(slug: str):
    """渲染落地页。TODO(一期)：slug → landing_page.html_content + 指纹采集 JS 注入。"""
    return f"<html><body>landing placeholder: {slug}</body></html>"


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
