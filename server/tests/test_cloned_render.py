"""克隆页静态渲染与消毒：Coremail 壳渲染、脚本剥离（口令红线）、表单重定向。"""
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.modules.template.models import LandingPage
from app.modules.template.service import render_cloned_html

# 合成 Coremail 登录页：与真实页同构——空壳 div + SYS_CONST Handlebars 模板 + CUSTOME_DATA
_COREMAIL_PAGE = """<!DOCTYPE html>
<html><head><title>Coremail邮件系统</title>
<base href="https://mail.example.com/coremail/common/index.jsp" />
</head><body>
<div class="main-bottom"></div>
<div class="main-middle"></div>
<div class="main">
    <div class="content"></div>
    <div class="aside"></div>
</div>
<script type="text/javascript">
var $, _, X = {$: 'login', r: '/coremail'};
CUSTOME_DATA = {"ts":1,"indexPageData2": {
'temp_resource':{'facade_custom':{'background_color':'#fff'}},
'real_resource':{
'detail_custom':{
'iac_enable':false,
'iac':[],
'telephone':[],
'top_link':[{'top_link_href':'http://help.example.com','top_link_content':'帮助'}]},
'facade_custom':{
'logo':['logo_001'],
'logo_link':'',
'background':['background_001'],
'favor_title':'Coremail',
'background_color':'#1b91e0',
'submit_button_color':'#3598db',
'submit_button_font_color':'rgb(255, 255, 255)',
'slogan_color':'#fff',
'slogan_text':'全终端同步 高效办公',
'slogan_fontsize':'14',
'copyright_link':'',
'copyright_text':'示例公司'}},
'style_used':'0'}};
SYS_CONST = {
    templates: {
'logoTpl':'<a href="{{#if facade_custom.logo_link}}{{facade_custom.logo_link}}{{^}}http://www.coremail.cn{{/if}}" class="logo"><img src="{{customLpImg facade_custom.logo \\'assets/logo.png\\'}}"></a>',
'contentTpl':'<div>{{> logoTpl}}</div>{{#if facade_custom.slogan_text}}<label class="slogan">{{facade_custom.slogan_text}}</label>{{/if}}<div class="copyright"><label>{{{facade_custom.copyright_text}}}</label></div>',
'asideTpl':'<div class="loginArea"><form action="/coremail/index.jsp" method="post" class="u-form"><input name="uid" type="text"><input name="password" type="password"><button class="u-btn u-btn-primary submit j-submit" type="button">登录</button>{{#if detail_custom.top_link}}{{#each detail_custom.top_link}}<a href="{{top_link_href}}">{{top_link_content}}</a>{{/each}}{{/if}}</form></div>'
    }
};
</script>
</body></html>
"""


def test_coremail_shell_rendered_statically():
    """JS 模板+数据渲染进静态壳：logo/背景/标语/版权/侧栏链接，与原站渲染一致。"""
    out = render_cloned_html(_COREMAIL_PAGE, "abcd1234", "tok-1", "https://mail.example.com/")
    assert 'class="logo"' in out
    assert "img_id=logo_001" in out
    assert "img_id=background_001" in out
    assert "示例公司" in out
    assert "全终端同步 高效办公" in out
    assert "帮助" in out
    # 背景/按钮配色以内联样式落地（原站 login 入口 chunk 的等价行为）
    assert "background-color:#1b91e0" in out
    assert "background-color:#3598db" in out
    # document.title 被原站 JS 设为 favor_title
    assert "<title>Coremail</title>" in out


def test_redline_scripts_stripped_form_rewritten():
    """红线：原站登录 JS 全剥离；表单重定向本服务；提交按钮改原生提交。"""
    out = render_cloned_html(_COREMAIL_PAGE, "abcd1234", "tok-1", "https://mail.example.com/")
    assert out.count("<script") == 1  # 仅剩指纹采集脚本
    assert "CUSTOME_DATA" not in out
    assert 'action="/p/abcd1234/submit"' in out
    assert 'name="token" value="tok-1"' in out
    assert '<button class="u-btn u-btn-primary submit j-submit" type="submit"' in out


def test_plain_page_sanitized_without_coremail_markers():
    """非 Coremail 页面：不渲染模板，但脚本剥离/表单重定向照常生效。"""
    page = (
        "<html><head><title>T</title></head><body>"
        "<script>evil()</script>"
        "<form action='https://real.com/login' method='post'><input name='password'></form>"
        "</body></html>"
    )
    out = render_cloned_html(page, "s1", "", "https://real.com/")
    assert "evil()" not in out
    assert 'action="/p/s1/submit"' in out
    assert 'method="post"' in out


def test_js_generated_form_gets_fallback():
    """表单完全由 JS 生成的页面：剥离脚本后注入兜底登录表单。"""
    page = (
        "<html><head></head><body>"
        "<div class='content'></div>"
        "<script>document.write('<form>')</script>"
        "</body></html>"
    )
    out = render_cloned_html(page, "s2", "")
    assert "<form" in out
    assert 'action="/p/s2/submit"' in out


def test_submit_base_absolute_action():
    """演练域名经 submit_base 传入：表单 action 为绝对 URL，不受克隆页 <base>（原站域名）劫持。"""
    page = _COREMAIL_PAGE.replace(
        'action="/coremail/index.jsp"',
        'action="/coremail/index.jsp"',  # 原站表单 action 被整体重写
    )
    out = render_cloned_html(
        page, "ab12", "tok-9", "https://mail.example.com/",
        submit_base="http://p.drill.example.com",
    )
    assert 'action="http://p.drill.example.com/p/ab12/submit"' in out
    # 带尾斜杠的 base 也归一化，不出现双斜杠
    out2 = render_cloned_html(
        page, "ab12", "", "https://mail.example.com/",
        submit_base="http://p.drill.example.com/",
    )
    assert 'action="http://p.drill.example.com/p/ab12/submit"' in out2
    # 兜底登录表单同样使用绝对 action
    bare = "<html><body><div class='content'></div></body></html>"
    out3 = render_cloned_html(
        bare, "ab12", "", "", submit_base="http://p.drill.example.com",
    )
    assert 'action="http://p.drill.example.com/p/ab12/submit"' in out3


def test_landing_serve_renders_cloned_page():
    """落地页服务 /p/{slug} 端到端：返回静态渲染+消毒后的页面，表单 action 用请求 host。"""
    db = SessionLocal()
    db.add(LandingPage(
        name="克隆-mail.example.com", type="cloned", slug="serve001",
        html_content=_COREMAIL_PAGE, source="cloned",
        clone_from_url="https://mail.example.com/", status="draft",
    ))
    db.commit()
    db.close()

    from landing.main import app as landing_app

    client = TestClient(landing_app)
    r = client.get("/p/serve001")
    assert r.status_code == 200
    body = r.text
    assert "img_id=logo_001" in body
    assert 'action="http://testserver/p/serve001/submit"' in body
    assert "CUSTOME_DATA" not in body
