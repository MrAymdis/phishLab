"""落地页自定义路径（仿真防识别）：路径校验、全局唯一、表单 action、邮件直链、/t/{token} 解析。"""
import pytest
from sqlalchemy import delete

from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.account.models import SysAccount
from app.modules.campaign.models import Campaign, CampaignTarget
from app.modules.campaign.render import render_campaign_email
from app.modules.org.models import EmpDept, EmpUser
from app.modules.settings.models import PlatformSetting
from app.modules.template.models import EmailTemplate, LandingPage
from app.modules.template.service import (
    _validate_custom_path,
    create_landing_page,
    render_cloned_html,
    update_landing_page,
)
from app.modules.tracking.stream import resolve_landing_path

TOKEN = "c" * 32


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (Campaign, CampaignTarget, EmpUser, EmpDept, EmailTemplate,
                  LandingPage, PlatformSetting):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _account(db):
    return db.get(SysAccount, 1)


# ---------- 路径校验 ----------

def test_validate_custom_path_ok():
    assert _validate_custom_path(None) is None
    assert _validate_custom_path("") is None
    assert _validate_custom_path("   ") is None
    assert _validate_custom_path("/") == "/"
    assert _validate_custom_path("/login.html") == "/login.html"
    assert _validate_custom_path("/" + "x" * 63) == "/" + "x" * 63  # 恰好 64 字符


def test_validate_custom_path_rejects():
    for bad in ("login.html",            # 无前导 /
                "/p/x", "/t/x", "/px/x", "/pa/x", "/learn/1", "/health",  # 平台保留路径
                "/a?b", "/a#b",          # 查询串/锚点
                "/" + "x" * 64):         # 超 64 字符
        with pytest.raises(BizError):
            _validate_custom_path(bad)


# ---------- 创建/更新与全局唯一 ----------

def test_create_landing_page_stores_custom_path():
    db = SessionLocal()
    pid = create_landing_page(db, _account(db),
                              {"name": "OA仿冒页", "type": "oa_login", "custom_path": "/"})
    assert db.get(LandingPage, pid).custom_path == "/"
    db.close()


def test_create_landing_page_duplicate_path_conflict():
    db = SessionLocal()
    acc = _account(db)
    create_landing_page(db, acc, {"name": "A", "type": "custom", "custom_path": "/login.html"})
    with pytest.raises(BizError):
        create_landing_page(db, acc, {"name": "B", "type": "custom", "custom_path": "/login.html"})
    db.close()


def test_update_landing_page_set_clear_and_conflict():
    db = SessionLocal()
    acc = _account(db)
    pid = create_landing_page(db, acc, {"name": "A", "type": "custom"})
    update_landing_page(db, acc, pid, {"custom_path": "/sso"})
    assert db.get(LandingPage, pid).custom_path == "/sso"
    update_landing_page(db, acc, pid, {"custom_path": ""})  # 空串清除 → 回退 /p/{slug}
    assert db.get(LandingPage, pid).custom_path is None
    # 占他人路径 → 冲突；清除后再占用 → 成功
    create_landing_page(db, acc, {"name": "B", "type": "custom", "custom_path": "/sso"})
    with pytest.raises(BizError):
        update_landing_page(db, acc, pid, {"custom_path": "/sso"})
    db.close()


# ---------- 渲染：表单 action 跟随自定义路径 ----------

def test_render_cloned_html_root_action():
    html = render_cloned_html("<html><body><form action='/x'></form></body></html>", "demo",
                              token=TOKEN, clone_from_url="https://oa.corp.com/login",
                              submit_base="https://oa-verify.cn", custom_path="/")
    assert 'action="https://oa-verify.cn/submit"' in html  # 根路径 → /submit（无 //submit）


def test_render_cloned_html_custom_path_action():
    html = render_cloned_html("<html><body></body></html>", "demo", token=TOKEN,
                              clone_from_url="",
                              submit_base="https://oa-verify.cn", custom_path="/login.html")
    assert 'action="https://oa-verify.cn/login.html/submit"' in html


def test_render_cloned_html_default_slug_action():
    html = render_cloned_html("<html><body><form action='/x'></form></body></html>", "demo",
                              token=TOKEN, submit_base="https://oa-verify.cn")
    assert 'action="https://oa-verify.cn/p/demo/submit"' in html  # 未配自定义路径 → 默认形态


# ---------- 邮件渲染：track_link 关闭时直连自定义路径 ----------

# ---------- 渲染：无 name 输入域补名（JS 提交型原站表单，脚本剥离后值会全部丢失） ----------

def test_render_fills_missing_input_names():
    html = render_cloned_html(
        '<html><body><form><input type="text" placeholder="请输入工号或邮箱">'
        '<input type="password" placeholder="请输入密码">'
        '<input type="text" id="verify">'
        '<input name="keep" value="1"></form></body></html>',
        "demo", token=TOKEN, submit_base="https://oa-verify.cn")
    assert 'name="请输入工号或邮箱"' in html   # placeholder 兜底
    assert 'name="password"' in html           # 密码框固定 password 系命名（口令分类）
    assert 'name="verify"' in html             # id 优先
    assert 'name="keep"' in html               # 已有 name 不动


def test_render_name_fill_skips_hidden_and_dedups():
    html = render_cloned_html(
        '<html><body><form><input type="hidden"><input type="submit" value="登录">'
        '<input type="text" placeholder="验证码">'
        '<input type="text" placeholder="验证码">'
        '</form></body></html>',
        "demo", token=TOKEN, submit_base="https://oa-verify.cn")
    # hidden/submit 不补名（原站 CSRF/按钮噪声）——原样保留，不新增 name
    assert '<input type="hidden">' in html
    assert '<input type="submit" value="登录">' in html
    # 同 placeholder 重名加序号
    assert 'name="验证码"' in html
    assert 'name="验证码_2"' in html


def test_render_email_track_link_off_uses_custom_path():
    db = SessionLocal()
    tpl = EmailTemplate(name="T", scene="notice", subject="S", html_body="<p>{{.ResetURL}}</p>",
                        track_pixel=1, track_link=0)
    db.add(tpl)
    db.flush()
    lp = LandingPage(name="LP", type="custom", slug="demo", custom_path="/")
    db.add(lp)
    db.flush()
    dept = EmpDept(name="D", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="U", email="u@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    c = Campaign(name="C", type="mail", creator_id=1, template_id=tpl.id,
                 landing_page_id=lp.id, target_mode="dept", target_snapshot={},
                 track_base_url="https://t.corp-drill.com", landing_base_url="https://oa-verify.cn")
    db.add(c)
    db.commit()
    html = render_campaign_email(db, c, user, TOKEN)["html"]
    assert "https://oa-verify.cn/" in html   # 根路径自定义
    assert "/p/" not in html                 # 不暴露平台默认形态
    db.close()


# ---------- 点击跳转解析：/t/{token} → (slug, custom_path) ----------

def _setup_campaign_with_token(db, custom_path=None):
    tpl = EmailTemplate(name="T", scene="notice", subject="S", html_body="<p>x</p>")
    db.add(tpl)
    db.flush()
    lp = LandingPage(name="LP", type="custom", slug="demo", custom_path=custom_path)
    db.add(lp)
    db.flush()
    dept = EmpDept(name="D", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="U", email="u@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    c = Campaign(name="C", type="mail", creator_id=1, template_id=tpl.id,
                 landing_page_id=lp.id, target_mode="dept", target_snapshot={})
    db.add(c)
    db.flush()
    db.add(CampaignTarget(campaign_id=c.id, user_id=user.id, token=TOKEN))
    db.commit()


def test_resolve_landing_path_returns_custom_path():
    db = SessionLocal()
    _setup_campaign_with_token(db, custom_path="/sso")
    slug, custom, landing_base = resolve_landing_path(TOKEN)
    assert (slug, custom) == ("demo", "/sso")
    assert isinstance(landing_base, str)
    assert resolve_landing_path("no-such-token")[:2] == (None, None)
    db.close()


def test_resolve_landing_path_falls_back_slug():
    db = SessionLocal()
    _setup_campaign_with_token(db)  # 未配自定义路径
    slug, custom, _ = resolve_landing_path(TOKEN)
    assert slug == "demo"
    assert custom is None
    db.close()
