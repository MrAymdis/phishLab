"""追踪/落地域基础 URL：设置页配置 → 渲染链接/像素生效，及更新接口校验器。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.core.config import settings as app_settings
from app.core.errors import BizError
from app.db.session import SessionLocal
from app.modules.campaign.models import Campaign
from app.modules.campaign.render import render_campaign_email
from app.modules.org.models import EmpDept, EmpUser
from app.modules.settings.models import PlatformSetting
from app.modules.settings.router import _validate_base_url
from app.modules.settings.service import resolve_track_urls
from app.modules.template.models import EmailTemplate, LandingPage

TOKEN = "b" * 32


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = SessionLocal()
    try:
        for m in (Campaign, EmpUser, EmpDept, EmailTemplate, LandingPage, PlatformSetting):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _setup(db, track_link: int = 1, track_base: str | None = None,
           landing_base: str | None = None):
    tpl = EmailTemplate(name="基础模板", scene="notice", subject="通知",
                        html_body="<p><a href='{{.ResetURL}}'>点此</a></p>",
                        track_pixel=1, track_link=track_link)
    db.add(tpl)
    db.flush()
    lp = LandingPage(name="仿冒登录页", type="mail_login", slug="demo-login")
    db.add(lp)
    db.flush()
    dept = EmpDept(name="财务部", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="李四", email="lisi@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    c = Campaign(name="基础演练", type="mail", creator_id=1, template_id=tpl.id,
                 landing_page_id=lp.id, target_mode="dept", target_snapshot={},
                 track_base_url=track_base, landing_base_url=landing_base)
    db.add(c)
    db.commit()
    return c, user


def test_resolve_track_urls_configured_pair():
    db = SessionLocal()
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com/"))
    db.add(PlatformSetting(setting_key="landing_base_url", setting_value="https://p.corp-drill.com/"))
    db.commit()
    assert resolve_track_urls(db) == ("https://t.corp-drill.com", "https://p.corp-drill.com")
    db.close()


def test_resolve_track_urls_single_side_ignored_dev():
    db = SessionLocal()
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com"))
    db.commit()
    # 成对生效：单边配置不生效，dev 回退端口直连兜底
    assert resolve_track_urls(db) == ("", "")
    db.close()


def test_render_uses_configured_base_urls():
    db = SessionLocal()
    c, user = _setup(db)
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com"))
    db.add(PlatformSetting(setting_key="landing_base_url", setting_value="https://p.corp-drill.com"))
    db.commit()

    html = render_campaign_email(db, c, user, TOKEN)["html"]
    assert f"https://t.corp-drill.com/t/{TOKEN}" in html          # 点击短链 → 追踪域
    assert f"https://t.corp-drill.com/px/{TOKEN}.gif" in html     # 打开像素 → 追踪域
    db.close()


def test_render_track_link_off_goes_landing_base():
    db = SessionLocal()
    c, user = _setup(db, track_link=0)
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com"))
    db.add(PlatformSetting(setting_key="landing_base_url", setting_value="https://p.corp-drill.com"))
    db.commit()

    html = render_campaign_email(db, c, user, TOKEN)["html"]
    assert f"https://p.corp-drill.com/p/demo-login" in html       # 关闭短链 → 直连落地域
    db.close()


def test_render_campaign_override_beats_global():
    db = SessionLocal()
    # 演练级成对覆盖（域名轮换场景）
    c, user = _setup(db, track_base="https://x.corp-drill.com", landing_base="https://y.corp-drill.com")
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com"))
    db.add(PlatformSetting(setting_key="landing_base_url", setting_value="https://p.corp-drill.com"))
    db.commit()

    html = render_campaign_email(db, c, user, TOKEN)["html"]
    assert f"https://x.corp-drill.com/t/{TOKEN}" in html          # 演练级覆盖优先
    assert f"https://x.corp-drill.com/px/{TOKEN}.gif" in html
    assert "https://t.corp-drill.com" not in html                 # 全局值未生效
    db.close()


def test_render_campaign_single_side_falls_back_global():
    db = SessionLocal()
    c, user = _setup(db, track_base="https://x.corp-drill.com")   # 只配单边 → 不生效
    db.add(PlatformSetting(setting_key="track_base_url", setting_value="https://t.corp-drill.com"))
    db.add(PlatformSetting(setting_key="landing_base_url", setting_value="https://p.corp-drill.com"))
    db.commit()

    html = render_campaign_email(db, c, user, TOKEN)["html"]
    assert f"https://t.corp-drill.com/t/{TOKEN}" in html          # 回落全局
    db.close()


def test_validate_base_urls_pair_and_same_host():
    from app.modules.campaign.service import _validate_base_urls

    with pytest.raises(BizError):  # 单边配置
        _validate_base_urls(SimpleNamespace(track_base_url="https://x.corp-drill.com",
                                            landing_base_url=None))
    with pytest.raises(BizError):  # 红线 3：与主平台同域
        _validate_base_urls(SimpleNamespace(track_base_url="https://admin.corp.com",
                                            landing_base_url="https://p.corp-drill.com"),
                            request_host="admin.corp.com")


def _req(host="admin.corp.com"):
    return SimpleNamespace(url=SimpleNamespace(hostname=host))


def test_validate_base_url_ok_and_normalized():
    assert _validate_base_url("track_base_url", "https://t.corp-drill.com/", _req()) \
        == "https://t.corp-drill.com"
    assert _validate_base_url("track_base_url", "", _req()) == ""  # 空串 = 清除配置


def test_validate_base_url_rejects_path_and_same_host():
    with pytest.raises(BizError):
        _validate_base_url("track_base_url", "https://t.corp-drill.com/p/x", _req())
    with pytest.raises(BizError):  # 红线 3：不得与主平台同域
        _validate_base_url("track_base_url", "https://admin.corp.com", _req())


def test_validate_base_url_prod_requires_https(monkeypatch):
    monkeypatch.setattr(app_settings, "env", "prod")
    with pytest.raises(BizError):
        _validate_base_url("track_base_url", "http://t.corp-drill.com", _req())
