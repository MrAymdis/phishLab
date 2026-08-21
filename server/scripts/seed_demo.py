"""演示数据种子脚本（幂等：先清空再插入，可重复执行）。

用法：python scripts/seed_demo.py
覆盖全部业务表：RBAC/组织/员工/素材/通道/演练/培训/报表/系统，支撑前端 11 个页面演示。
注意：target_count 为展示规模数，campaign_target 仅存演示子集（~20 行），
比率由 campaign_stat / target_count 现算 —— 演示可接受。
"""
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.security import encrypt_secret, hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

# ============ 各模块模型 ============
from app.modules.account.models import LoginLog, SysAccount  # noqa: E402
from app.modules.ai.models import AiDraft, AiMessage, AiProvider, AiSession  # noqa: E402
from app.modules.analytics.models import StatDaily  # noqa: E402
from app.modules.campaign.models import (  # noqa: E402
    Campaign, CampaignAlert, CampaignBatch, CampaignStat, CampaignTarget,
)
from app.modules.channel.models import (  # noqa: E402
    PhishDomain, SendChannel, SendQuotaUsage, SenderProfile,
)
from app.modules.integration.models import SiemConfig, WebhookConfig  # noqa: E402
from app.modules.license.models import LicenseInfo, LicenseUsage  # noqa: E402
from app.modules.openapi_mod.models import OpenApiLog, OpenApp  # noqa: E402
from app.modules.org.models import (  # noqa: E402
    EmpDept, EmpRiskProfile, EmpTag, EmpUser, EmpUserTag,
)
from app.modules.rbac.models import (  # noqa: E402
    AuditLog, SysAccountRole, SysPermission, SysRole, SysRolePermission,
)
from app.modules.report.models import MailReport, ReportRewardLog  # noqa: E402
from app.modules.settings.models import PlatformSetting  # noqa: E402
from app.modules.template.models import (  # noqa: E402
    AttachmentPayload, EmailTemplate, LandingFormField, LandingPage, QrAsset,
)
from app.modules.tracking.models import Fingerprint, TrackEvent  # noqa: E402
from app.modules.training.models import (  # noqa: E402
    Course, ExamPaper, ExamPaperQuestion, ExamQuestion, ExamRecord,
    TrainingAssignment, TrainingTask,
)

NOW = datetime.now()
TODAY = NOW.date()

# 清空顺序（先子后父；无外键约束，纯 DELETE 即可）
TRUNCATE_TABLES = [
    "ai_message", "ai_session", "ai_draft", "ai_usage_stat", "ai_provider",
    "open_api_log", "open_app",
    "audit_log", "login_log",
    "sys_account_role", "sys_role_permission", "sys_role_dept", "sys_role", "sys_permission",
    "platform_setting", "webhook_config", "siem_config",
    "license_usage", "license",
    "stat_daily",
    "mail_report", "report_reward_log",
    "track_event", "fingerprint",
    "campaign_alert", "campaign_batch", "campaign_stat", "campaign_target", "campaign",
    "training_assignment", "exam_record", "exam_paper_question", "exam_paper", "exam_question",
    "training_task", "course",
    "qr_asset", "attachment_payload", "landing_form_field", "landing_page", "email_template",
    "send_quota_usage", "phish_domain", "sender_profile", "send_channel",
    "emp_user_tag", "emp_tag", "emp_group_member", "emp_group",
    "emp_risk_profile", "emp_user", "emp_dept",
    "org_sync_job", "attachment_download_log",
    "sys_account",
]


def seed_rbac(db):
    """1. RBAC：admin + 3 角色 + 11 菜单权限 + 绑定。"""
    admin = SysAccount(
        id=1, username="admin",
        password_hash=hash_password("PhishLab@2026"),
        real_name="超级管理员", status=1, last_login_at=NOW,
    )
    db.add(admin)

    roles = [
        SysRole(id=1, code="super_admin", name="超级管理员", data_scope=1, remark="拥有所有权限"),
        SysRole(id=2, code="operator", name="演练操作员", data_scope=3, remark="可发起/管理演练与素材"),
        SysRole(id=3, code="auditor", name="只读审计员", data_scope=4, remark="仅可查看报表与日志"),
    ]
    db.add_all(roles)

    menus = [
        ("数据概览", "/dashboard"), ("演练管理", "/campaign"), ("素材模板", "/template"),
        ("发送配置", "/send-config"), ("用户和组", "/users"), ("安全培训", "/training"),
        ("数据报表", "/reports"), ("邮件举报", "/mail-report"), ("系统设置", "/settings"),
        ("智能助手", "/ai"), ("API开放平台", "/openapi"),
    ]
    perms = [
        SysPermission(id=i + 1, parent_id=0, name=n, perm_code=f"menu:{p}", type=1, route=p, sort=i)
        for i, (n, p) in enumerate(menus)
    ]
    db.add_all(perms)

    # 接口/按钮级操作权限（require_perm 校验；写操作默认拒绝，红线相关）
    # parent_id 挂到对应菜单权限点（前端树状展示：菜单 → 功能）
    menu_id = {f"menu:{p}": i + 1 for i, (_n, p) in enumerate(menus)}
    op_perms = [
        ("campaign:create", "演练管理", "创建/复制演练"),
        ("campaign:control", "演练管理", "启动/暂停/恢复/终止/暂存/测试发送"),
        ("campaign:delete", "演练管理", "删除演练"),
        ("campaign:reveal", "演练管理", "提交事件取证解密（红线）"),
        ("channel:manage", "发送配置", "通道/域名/伪装发件人增删改与测试发信"),
        ("template:manage", "素材模板", "邮件模板/落地页增删改与克隆（红线）"),
        ("settings:manage", "系统设置", "平台参数修改（留存期等红线配置）"),
        ("license:manage", "系统设置", "License 激活/离线导入"),
        ("report:classify", "邮件举报", "举报人工研判"),
        ("org:manage", "用户和组", "部门/员工/标签增删改"),
        ("training:manage", "安全培训", "课程/培训任务增删改"),
        ("ai:review", "智能助手", "AI 草稿审核（入库/丢弃）"),
        ("openapi:manage", "API开放平台", "开放平台应用创建/管理"),
    ]
    op_rows = [
        SysPermission(
            parent_id=menu_id[f"menu:{n}"], name=n, perm_code=code, type=3, route="", sort=1000 + i,
        )
        for i, (code, n, _remark) in enumerate(op_perms)
    ]
    db.add_all(op_rows)
    db.flush()

    db.add(SysAccountRole(account_id=1, role_id=1))
    db.add_all(SysRolePermission(role_id=1, permission_id=p.id) for p in perms)
    # super_admin 在 require_perm 代码层放行；operator 绑定运营类操作权限 + 对应菜单可见
    operator_codes = {
        c for c, _n, _r in op_perms
        if c.startswith(("campaign:", "channel:", "template:", "org:", "training:", "report:", "ai:"))
    }
    db.add_all(
        SysRolePermission(role_id=2, permission_id=p.id)
        for p in op_rows if p.perm_code in operator_codes
    )
    # operator：菜单可见（数据概览/演练/模板/发送配置/用户组/培训/报表/举报/AI）
    db.add_all(
        SysRolePermission(role_id=2, permission_id=menu_id[m])
        for m in ("menu:/dashboard", "menu:/campaign", "menu:/template", "menu:/send-config",
                  "menu:/users", "menu:/training", "menu:/reports", "menu:/mail-report", "menu:/ai")
    )
    # auditor：只读报表与审计日志（数据概览/演练/报表/系统设置）
    db.add_all(
        SysRolePermission(role_id=3, permission_id=menu_id[m])
        for m in ("menu:/dashboard", "menu:/campaign", "menu:/reports", "menu:/settings")
    )
    db.flush()


def seed_org(db):
    """2. 组织：11 部门、5 标签、20 员工 + 风险画像 + 标签 + 培训分配。"""
    depts = [
        (1, 0, "总公司"),
        (2, 1, "技术部"), (3, 1, "财务部"), (4, 1, "人力资源部"),
        (5, 1, "市场部"), (6, 1, "行政部"),
        (7, 2, "研发组"), (8, 2, "运维组"), (9, 2, "安全组"),
        (10, 3, "会计组"), (11, 3, "出纳组"),
    ]
    for did, pid, name in depts:
        db.add(EmpDept(id=did, parent_id=pid, path="", name=name, source="manual"))
    db.flush()
    # 回填 path
    for did, pid, _ in depts:
        node = db.get(EmpDept, did)
        parent_path = db.get(EmpDept, pid).path if pid else ""
        node.path = f"{parent_path}{did}/"
    db.flush()

    tags = [
        (1, "高管", "#E6A23C"), (2, "研发", "#378ADD"), (3, "运维", "#0D9488"),
        (4, "财务", "#A05B8C"), (5, "新员工", "#67C23A"),
    ]
    for tid, name, color in tags:
        db.add(EmpTag(id=tid, name=name, color=color))

    # (id, 工号, 姓名, dept_id, 岗位, 邮箱, 手机, 风险分, 中招次数, 培训状态, tag_ids)
    # 培训状态: completed→completed / progress→learning / none→无分配
    users = [
        (1, "EMP001", "张伟", 7, "高级研发工程师", "zhangwei@jianfa.com", "13812342856", 82, 3, "completed", [2]),
        (2, "EMP002", "李婷", 7, "研发工程师", "liting@jianfa.com", "13922549873", 55, 1, "progress", [2]),
        (3, "EMP003", "王强", 8, "运维工程师", "wangqiang@jianfa.com", "13755661234", 48, 1, "completed", [3]),
        (4, "EMP004", "赵敏", 10, "会计", "zhaomin@jianfa.com", "13677889900", 88, 4, "none", [4]),
        (5, "EMP005", "钱磊", 11, "出纳", "qianlei@jianfa.com", "13599001122", 78, 3, "progress", [4]),
        (6, "EMP006", "孙丽", 3, "财务经理", "sunli@jianfa.com", "13411223344", 72, 2, "completed", [1, 4]),
        (7, "EMP007", "周涛", 7, "研发工程师", "zhoutao@jianfa.com", "13344556677", 22, 0, "completed", [2]),
        (8, "EMP008", "吴静", 4, "HRBP", "wujing@jianfa.com", "13266778899", 52, 1, "progress", [5]),
        (9, "EMP009", "郑浩", 5, "市场专员", "zhenghao@jianfa.com", "13177889900", 65, 2, "completed", []),
        (10, "EMP010", "冯雪", 5, "品牌专员", "fengxue@jianfa.com", "13088990011", 45, 1, "completed", []),
        (11, "EMP011", "陈晨", 6, "行政主管", "chenchen@jianfa.com", "18900112233", 35, 1, "completed", []),
        (12, "EMP012", "褚健", 7, "安全工程师", "chujian@jianfa.com", "18811223344", 15, 0, "completed", [2]),
        (13, "EMP013", "卫兰", 10, "会计", "weilan@jianfa.com", "18722334455", 75, 3, "none", [4]),
        (14, "EMP014", "蒋敏", 4, "HRBP", "jiangmin@jianfa.com", "18633445566", 28, 0, "completed", [5]),
        (15, "EMP015", "沈飞", 5, "市场经理", "shenfei@jianfa.com", "18544556677", 58, 1, "completed", []),
        (16, "EMP016", "韩雪", 6, "行政专员", "hanxue@jianfa.com", "18455667788", 18, 0, "completed", [5]),
        (17, "EMP017", "杨帆", 8, "运维工程师", "yangfan@jianfa.com", "18366778899", 50, 1, "completed", [3]),
        (18, "EMP018", "朱婷", 5, "市场专员", "zhuting@jianfa.com", "18277889900", 42, 1, "progress", []),
        (19, "EMP019", "秦朗", 7, "研发工程师", "qinlang@jianfa.com", "18188990011", 12, 0, "completed", [2, 5]),
        (20, "EMP020", "许静", 3, "财务总监", "xujing@jianfa.com", "18099001122", 68, 2, "completed", [1, 4]),
    ]
    for uid, no, name, dept_id, pos, email, mobile, score, clicks, train, tag_ids in users:
        db.add(EmpUser(
            id=uid, emp_no=no, name=name, email=email,
            mobile_enc=encrypt_secret(mobile), dept_id=dept_id, position=pos,
            status=1, initial_risk=score, source="manual",
        ))
        db.add(EmpRiskProfile(
            user_id=uid,
            total_score=score,
            email_recognize=min(100, max(0, score - 20)),
            link_click=min(100, max(0, score + 10)),
            pwd_submit=min(100, max(0, score + 25)),
            attach_run=min(100, max(0, score - 5)),
            report_awareness=min(100, max(0, 100 - score)),
            phish_count=clicks,
            report_count=clicks,
            training_completion=Decimal(100 if train == "completed" else (60 if train == "progress" else 0)),
            risk_level=1 if score <= 70 else (3 if score >= 81 else 2),
        ))
        for tid in tag_ids:
            db.add(EmpUserTag(user_id=uid, tag_id=tid))
    db.flush()


def seed_license(db):
    """3. License：trial + 月度用量。"""
    db.add(LicenseInfo(
        id=1, license_key="PL-TRIAL-1DEMO2026", edition="trial", customer_name="演示客户",
        user_quota=5000, mail_quota=300000, sms_quota=10000, campaign_quota=200,
        activate_mode="online", activated_at=NOW - timedelta(days=90),
        expire_at=NOW + timedelta(days=14), status="active",
    ))
    for i in range(3):
        db.add(LicenseUsage(
            stat_date=(TODAY.replace(day=1) - timedelta(days=30 * i)).replace(day=1),
            mails_sent=182000 if i == 0 else (150000 if i == 1 else 120000),
            sms_sent=2000, campaigns_created=12 if i == 0 else 9,
        ))
    db.flush()


TEMPLATE_BODIES = {
    1: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>系统检测到您的 OA 账号密码将于 <b style="color:#d93025">24 小时后过期</b>，过期后将无法登录 OA 系统处理待办事项。</p>
  <p>为保障您的正常工作，请尽快点击下方链接完成密码重置：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">立即重置密码</a></p>
  <p>如非本人操作，请忽略本邮件并及时联系 IT 运维部。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>IT 运维部 · 系统通知</p>
</div>""",
        2: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>提醒您：<b>Q2 差旅报销</b>将于本周五 18:00 截止。经核查，您名下仍有 <b>3 笔差旅单据</b>未完成提交。</p>
  <p>逾期未提交的单据将顺延至下季度报销，请点击下方链接登录 OA 完成单据提交：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">前往提交报销单</a></p>
  <p>如有疑问请联系财务部报销组（分机 8801）。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>财务部 · 报销管理组</p>
</div>""",
        3: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>2026 年度员工满意度调查现已开启，您的意见将直接帮助我们改进工作环境与福利体系。</p>
  <p>问卷预计耗时 5 分钟，<b>8 月 20 日前</b>完成可参与抽奖赢取京东卡：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">开始填写问卷</a></p>
  <p>本次调查匿名进行，请放心填写。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>人力资源部 · 员工服务组</p>
</div>""",
        4: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>为提升邮箱系统稳定性，我们将于<b>本周六凌晨 2:00 - 6:00</b>进行企业邮箱系统升级维护。</p>
  <p>升级完成后，您的邮箱账号需<b>重新验证</b>方可正常收发邮件，请提前点击下方链接完成验证预约：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">立即验证账户</a></p>
  <p>升级期间不影响已收取的邮件，给您带来不便敬请谅解。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>IT 运维部 · 系统通知</p>
</div>""",
        5: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>🎉 恭喜您！在公司 10 周年庆典抽奖活动中，您幸运地获得了<b style="color:#d93025">一等奖 iPhone 16 Pro</b>！</p>
  <p>请于 <b>3 个工作日内</b>点击下方链接填写领奖信息，逾期视为自动放弃：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">填写领奖信息</a></p>
  <p>奖品将在信息确认后 7 个工作日内发放。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>行政部 · 员工活动组</p>
</div>""",
        6: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>端午将至，公司为每位员工准备了<b>粽子礼盒</b>一份，请点击下方链接登记收货信息：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">登记收货地址</a></p>
  <p>我们将于 5 月 30 日前统一寄出，请确保地址信息准确。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>行政部 · 员工福利组</p>
</div>""",
        7: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p>财务部重要通知：由于供应商账户调整，<b>即日起原 XX 公司付款账户变更为新账户</b>。</p>
  <p>请点击下方链接查看并确认最新付款信息，以免影响后续款项支付：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#378ADD;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">查看变更详情</a></p>
  <p style="color:#d93025">如收到非本渠道的付款信息变更通知，请立即联系财务部核实。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>财务部 · 资金管理组</p>
</div>""",
        8: """
<div style="font-family:'Microsoft YaHei',sans-serif;font-size:14px;color:#333;line-height:1.8">
  <p>{{.FirstName}}，您好：</p>
  <p style="color:#d93025"><b>【紧急】</b>系统检测到您的 VPN 账号存在异常登录行为，账号将于 <b>24 小时后冻结</b>。</p>
  <p>如非本人操作，请立即点击下方链接完成身份验证并重置密码：</p>
  <p style="margin:16px 0"><a href="{{.ResetURL}}" style="background:#d93025;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none">立即验证并解冻</a></p>
  <p>冻结期间将无法访问公司内网资源。</p>
  <p style="color:#888;font-size:12px;margin-top:24px">此邮件由系统自动发送，请勿直接回复。<br>IT 运维部 · 安全响应组</p>
</div>""",
}


def seed_template(db):
    """4. 素材：8 邮件模板、6 落地页 + 表单字段、8 载荷、2 二维码。"""
    templates = [
        (1, "OA密码过期提醒", "upgrade", "【重要通知】您的OA系统密码将于24小时后过期", "IT运维部", 4, 234, Decimal("28.4")),
        (2, "Q2差旅报销截止提醒", "finance", "【财务通知】Q2差旅报销截止提醒", "财务部", 3, 156, Decimal("24.1")),
        (3, "年度员工满意度调查", "hr", "【HR】2026年度员工满意度调查", "人力资源部", 2, 98, Decimal("18.6")),
        (4, "企业邮箱系统升级公告", "upgrade", "【IT运维】企业邮箱系统升级公告", "IT运维部", 3, 89, Decimal("21.2")),
        (5, "公司周年庆抽奖通知", "lottery", "恭喜您获得公司周年庆一等奖", "行政部", 2, 87, Decimal("31.8")),
        (6, "端午节福利领取登记", "holiday", "【端午福利】粽子礼盒领取登记", "行政部", 1, 62, Decimal("15.9")),
        (7, "供应商付款信息变更", "finance", "供应商付款信息变更（重要）", "财务部", 5, 43, Decimal("26.7")),
        (8, "VPN账号即将冻结", "alert", "【紧急】VPN账号即将冻结，请点击完成验证", "IT运维部", 4, 31, Decimal("33.5")),
    ]

    for tid, name, scene, subject, sender, stars, used, click in templates:
        db.add(EmailTemplate(
            id=tid, name=name, scene=scene, subject=subject,
            html_body=TEMPLATE_BODIES[tid],
            variables=["{{.FirstName}}", "{{.Department}}", "{{.ResetURL}}"],
            source="builtin", status="approved", sender=sender,
            stars=stars, used_count=used, click_rate=click,
        ))


    landings = [
        (1, "企业邮箱登录页", "mail_login", "#378ADD"),
        (2, "泛微OA 统一认证", "oa_login", "#52c41a"),
        (3, "企业网盘身份验证", "pan_auth", "#faad14"),
        (4, "钉钉工作台登录", "custom", "#722ed1"),
        (5, "飞书账号安全验证", "custom", "#13c2c2"),
        (6, "Outlook Web 登录", "mail_login", "#0078d4"),
    ]
    for lid, name, type_, color in landings:
        db.add(LandingPage(
            id=lid, name=name, type=type_, slug=f"demo{lid:02d}{lid * 7:x}",
            form_schema={"collect": 5, "fields": [
                {"field_key": "username", "label": "用户名"},
                {"field_key": "password", "label": "密码", "sensitive_flag": 1},
                {"field_key": "sms_code", "label": "验证码"},
            ]},
            source="builtin", status="approved", used_count=(lid * 23) % 90 + 12,
        ))
    db.flush()
    for lid in range(1, 7):
        for i, f in enumerate(["username", "password", "sms_code"]):
            db.add(LandingFormField(
                page_id=lid, field_key=f,
                label={"username": "用户名", "password": "密码", "sms_code": "验证码"}[f],
                sensitive_flag=1 if f == "password" else 0, sort=i,
            ))

    payloads = [
        (1, "差旅费报销单_宏启用版.xls", "macro_doc", "Windows", 76, 89, "📊"),
        (2, "员工信息采集表.xlsm", "macro_doc", "Windows", 82, 67, "📊"),
        (3, "绩效考核表_Q2.xls", "macro_doc", "Windows", 71, 112, "📊"),
        (4, "采购订单模板_带宏.docm", "macro_doc", "Windows/macOS", 79, 34, "📄"),
        (5, "installer_setup_x64.exe", "exe", "Windows", 96, 0, "💻"),
        (6, "update_patch.exe", "exe", "Windows", 97, 0, "💻"),
        (7, "会议邀请二维码", "qr", "通用", 100, 58, "🔳"),
        (8, "WiFi认证二维码", "qr", "通用", 100, 41, "🔳"),
    ]
    for pid, name, ftype, platform, evade, used, icon in payloads:
        db.add(AttachmentPayload(
            id=pid, name=name, file_type=ftype, file_path=f"minio://payload/{name}",
            file_hash=f"{pid:08x}" * 8, file_size=200_000 + pid * 30_000,
            platform=platform, evade_rate=evade, used_count=used,
            status="enabled" if pid <= 4 else "disabled", icon=icon,
        ))
    db.add(QrAsset(id=1, name="会议邀请二维码", landing_page_id=1, short_code="mt1nv9", img_path="minio://qr/mt1nv9.png"))
    db.add(QrAsset(id=2, name="WiFi认证二维码", landing_page_id=2, short_code="w2kq7d", img_path="minio://qr/w2kq7d.png"))
    db.flush()


def seed_channel(db):
    """5. 通道：6 通道（含加密口令）、5 伪装发件人、4 域名、配额。"""
    channels = [
        (1, "主SMTP服务器", "smtp", "smtp1.company.com", 465, "ssl", "notify@drill-domain.com", "normal", 95, 62),
        (2, "备用SMTP服务器", "smtp", "smtp2.company.com", 587, "starttls", "notify2@drill-domain.com", "normal", 88, 41),
        (3, "Exchange 邮件服务器", "ews", None, None, None, None, "normal", 91, 55),
        (4, "阿里云短信通道", "sms", None, None, None, None, "normal", 85, 70),
        (5, "腾讯云短信通道", "sms", None, None, None, None, "abnormal", 62, 45),
        (6, "自定义HTTP短信网关", "sms", None, None, None, None, "normal", 78, 52),
    ]
    for cid, name, ctype, host, port, encrypt, smtp_user, status, score, latency in channels:
        kw = {
            "name": name, "type": ctype, "status": status,
            "daily_limit": 5000 if cid != 2 else 2000,
            "is_default": 1 if cid == 1 else 0,
            "last_test_result": {"ok": status == "normal", "score": score,
                                  "latency_ms": latency, "message": "连通性正常" if status == "normal" else "连接超时"},
            "last_test_at": NOW - timedelta(hours=cid),
        }
        if ctype == "smtp":
            kw.update(smtp_host=host, smtp_port=port, smtp_encrypt=encrypt,
                      smtp_username=smtp_user, smtp_password_enc=encrypt_secret("Demo@Pass123"))
        elif ctype == "ews":
            kw.update(ews_url="https://mail.company.com/EWS/Exchange.asmx",
                      ews_username="drill@company.com",
                      ews_password_enc=encrypt_secret("Demo@Pass123"), ews_auth_mode="basic")
        else:
            kw.update(sms_provider=["aliyun", "tencent", "custom_http"][cid - 4],
                      sms_api_url="https://sms.example.com/send" if cid == 6 else None,
                      sms_sign="安全通知", sms_key="LTAI5tDemoKey",
                      sms_secret_enc=encrypt_secret("DemoSmsSecret"))
        db.add(SendChannel(id=cid, **kw))
    db.flush()

    senders = [
        (1, "财务部-王会计", "mail", "财务部 · 王会计", "caiwu@drill-domain.com", "no-reply@company.com", ["财务类"]),
        (2, "HR-员工服务", "mail", "人力资源部 · 员工服务", "hr@drill-domain.com", None, ["HR类"]),
        (3, "IT运维-系统通知", "mail", "IT运维部 · 系统通知", "it@drill-domain.com", None, ["系统类"]),
        (4, "行政部-福利发放", "mail", "行政部 · 福利发放", "admin@drill-domain.com", None, ["节假日", "中奖类"]),
        (5, "安全告警中心", "sms", "安全告警中心", None, None, ["安全类"]),
    ]
    for sid, name, ctype, display, addr, reply, scenes in senders:
        db.add(SenderProfile(
            id=sid, name=name, channel_type=ctype, display_name=display,
            from_addr=addr, reply_to=reply,
            sms_number="1069001234" if ctype == "sms" else None,
            sms_sign="安全通知" if ctype == "sms" else None,
            scene_tags=scenes,
        ))

    domains = [
        (1, "drill-domain.com", 99, "ok", "ok", "ok"),
        (2, "phish-mail.cn", 93, "ok", "ok", "fail"),
        (3, "oa-verify.cn", 85, "ok", "fail", "fail"),
        (4, "sec-alert.top", 62, "fail", "fail", "fail"),
    ]
    for did, domain, score, spf, dkim, dmarc in domains:
        db.add(PhishDomain(
            id=did, domain=domain, purpose="演练发件域名",
            spf_status=spf, dkim_status=dkim, dmarc_status=dmarc, mx_status="ok",
            deliver_score=score,
            repair_tips="SPF: v=spf1 include:spf.mail-provider.com ~all\nDKIM: 添加 TXT 记录 phish._domainkey\nDMARC: v=DMARC1; p=none",
            dkim_selector="phish", dkim_public_key="-----BEGIN PUBLIC KEY-----\ndemo\n-----END PUBLIC KEY-----",
            dkim_private_key_enc=encrypt_secret("-----BEGIN PRIVATE KEY-----\ndemo\n-----END PRIVATE KEY-----"),
            last_check_at=NOW - timedelta(days=1), status="active",
        ))
    db.add(SendQuotaUsage(channel_id=1, stat_date=TODAY, sent_count=12860))
    db.flush()


def seed_campaign(db):
    """6. 演练：6 场（多状态）+ 统计 + 目标子集 + 批次 + 预警 + 追踪事件 + 指纹。"""
    campaigns = [
        dict(id=1, name="Q3全员防钓鱼演练", type="mail", status="running",
             start=NOW - timedelta(days=1), end=NOW + timedelta(days=6),
             target=3580, stat=(2560, 967, 573, 798)),
        dict(id=2, name="财务人员专项演练", type="mail", status="scheduled",
             start=NOW + timedelta(days=10), end=NOW + timedelta(days=12),
             target=56, stat=None),
        dict(id=3, name="Q2全员钓鱼演练", type="mail", status="completed",
             start=NOW - timedelta(days=67), end=NOW - timedelta(days=59),
             target=3512, stat=(2390, 1089, 667, 690)),
        dict(id=4, name="短信钓鱼试点", type="sms", status="completed",
             start=NOW - timedelta(days=88), end=NOW - timedelta(days=86),
             target=420, stat=(218, 76, 34, 22)),
        dict(id=5, name="USB投放测试（研发楼）", type="usb", status="terminated",
             start=NOW - timedelta(days=136), end=NOW - timedelta(days=135),
             target=200, stat=(80, 24, 10, 4)),
        dict(id=6, name="新员工安全意识测试", type="mail", status="paused",
             start=NOW - timedelta(days=6), end=NOW + timedelta(days=4),
             target=30, stat=(19, 7, 3, 5)),
    ]
    for c in campaigns:
        kw = dict(
            id=c["id"], name=c["name"], description=f"{c['name']}（演示数据）", type=c["type"],
            status=c["status"], creator_id=1, template_id=1, landing_page_id=1,
            channel_id=1, sender_profile_id=1, domain_id=1,
            target_mode="dept", target_snapshot={"dept_ids": [1]},
            target_count=c["target"],
            schedule_type="timed" if c["status"] == "scheduled" else "now",
            schedule_at=c["start"], batch_count=3, batch_interval_min=30,
            randomize_content=1, time_jitter_sec=60, pixel_degrade=0,
            training_policy="redirect", course_ids=[2],
            force_training_rules=[{"event": "submit", "force": True}],
            auth_confirmed=1,
            started_at=c["start"] if c["status"] in ("running", "completed", "paused", "terminated") else None,
            ended_at=c["end"] if c["status"] in ("completed", "terminated") else None,
        )
        db.add(Campaign(**kw))
    db.flush()

    # campaign_stat（演示规模下的行为计数，比率与前端 mock 一致）
    for c in campaigns:
        if c["stat"] is None:
            db.add(CampaignStat(campaign_id=c["id"]))
            continue
        delivered, open_, click, submit = c["stat"]
        db.add(CampaignStat(
            campaign_id=c["id"], delivered_cnt=delivered, open_cnt=open_,
            click_cnt=click, submit_cnt=submit,
            report_cnt=int(submit * 0.9),
        ))
        db.add(CampaignBatch(campaign_id=c["id"], batch_no=1, plan_at=c["start"],
                             status="done", sent_count=min(delivered, 1200),
                             started_at=c["start"], finished_at=c["start"] + timedelta(hours=2)))
    db.flush()

    # campaign_target：演练 1 的员工子集（含打开/点击/提交标记）
    target_rows = [
        (1, 1, 2, 0, 0), (2, 4, 3, 1, 1), (3, 5, 2, 1, 0), (4, 6, 1, 0, 0),
        (5, 9, 2, 1, 0), (6, 10, 1, 0, 0), (7, 13, 2, 1, 1), (8, 16, 1, 0, 0),
        (9, 18, 1, 0, 0), (10, 20, 2, 1, 0),
    ]
    for cid_, uid, opens, clicked, submitted in target_rows:
        db.add(CampaignTarget(
            campaign_id=cid_, user_id=uid, batch_no=1,
            token=f"{uid:08x}{cid_:04x}" + "0" * 20,  # 32位
            send_status="delivered", sent_at=NOW - timedelta(days=1),
            delivered_at=NOW - timedelta(days=1),
            open_count=opens, first_open_at=NOW - timedelta(hours=20) if opens else None,
            last_open_at=NOW - timedelta(hours=5) if opens else None,
            click_count=clicked, first_click_at=NOW - timedelta(hours=18) if clicked else None,
            submit_flag=submitted, submit_at=NOW - timedelta(hours=18) if submitted else None,
            report_flag=1 if uid in (10, 16) else 0,
            report_at=NOW - timedelta(hours=2) if uid in (10, 16) else None,
        ))

    alerts = [
        (1, "pwd_submit", 3, "张伟 在演练落地页提交了密码格式输入，属高危行为", 1),
        (2, "dept_threshold", 2, "财务部中招率超过 30% 阈值，建议启动专项培训", None),
        (3, "fast_submit", 2, "赵敏 打开邮件后 8 秒内完成提交，风险意识薄弱", 4),
    ]
    for aid, atype, level, msg, uid in alerts:
        db.add(CampaignAlert(id=aid, campaign_id=1, type=atype, level=level,
                             message=msg, target_user_id=uid))

    # 追踪事件（=监控页时间轴）
    events = [
        ("submit", 1, NOW - timedelta(minutes=32), "在登录页提交了敏感数据"),
        ("click", 4, NOW - timedelta(minutes=58), "点击了邮件中的链接"),
        ("open", 5, NOW - timedelta(minutes=95), "打开了邮件"),
        ("report", 10, NOW - timedelta(hours=2), "通过 Outlook 插件举报可疑邮件"),
        ("submit", 13, NOW - timedelta(hours=3), "在登录页提交了敏感数据"),
    ]
    for i, (etype, uid, ts, detail) in enumerate(events):
        db.add(TrackEvent(
            id=i + 1, campaign_id=1, user_id=uid, token=f"{uid:08x}",
            event_type=etype, ip=f"10.12.{uid}.{i + 10}",
            ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0",
            detail={"desc": detail},
        ))

    for i, (fp, seen) in enumerate([
        ("a1b2c3d4e5f60718293a4b5c6d7e8f90", 612),
        ("f90e8d7c6b5a4938271605e4d3c2b1a0", 208),
        ("1234567890abcdef1234567890abcdef", 141),
        ("fedcba0987654321fedcba0987654321", 39),
    ]):
        db.add(Fingerprint(id=i + 1, fp_hash=fp, first_seen_at=NOW - timedelta(days=6),
                           last_seen_at=NOW - timedelta(hours=i), seen_count=seen))
    db.flush()


def seed_training(db):
    """7. 培训：6 课程、6 任务、7 题目、5 试卷 + 关联 + 考试记录。"""
    courses = [
        (1, "《信息安全基础规范》", "video", 28, "easy", "视频课件", 3420, 91),
        (2, "《钓鱼邮件识别入门》", "article", 18, "easy", "图文+PDF", 3210, 88),
        (3, "《钓鱼邮件识别进阶》", "interactive", 45, "hard", "场景模拟", 2156, 72),
        (4, "《企业数据安全红线》", "pdf", 12, "mid", "PDF文档", 2980, 85),
        (5, "《财务人员专项安全课》", "video", 52, "hard", "视频+案例", 580, 68),
        (6, "《新员工入职安全培训》", "interactive", 90, "mid", "完整培训包", 186, 92),
    ]
    for cid, title, ctype, dur, level, material, learners, completion in courses:
        db.add(Course(id=cid, title=title, type=ctype, duration_min=dur, level=level,
                      material=material, description=f"{title} 课程描述", source="builtin",
                      status="approved", created_by=1))

    tasks = [
        (1, "Q3全员安全意识强化任务", 1, "全员", NOW + timedelta(days=14), "active", 3580, 1920, 2860),
        (2, "财务中招人员强制培训", 5, "财务部", NOW + timedelta(days=4), "active", 56, 38, 52),
        (3, "高管专项合规培训", 4, "高管组", NOW - timedelta(days=16), "closed", 12, 12, 12),
        (4, "Q2新员工入职培训", 6, "新员工组", NOW - timedelta(days=37), "closed", 28, 26, 28),
        (5, "5月钓鱼识别进阶训练", 3, "市场+行政", NOW - timedelta(days=88), "active", 160, 118, 142),
        (6, "研发部安全基础测评", 1, "研发部", NOW - timedelta(days=108), "closed", 342, 342, 342),
    ]
    for tid, name, course_id, audience, deadline, status, cnt, done, started in tasks:
        db.add(TrainingTask(
            id=tid, name=name, source="manual", campaign_id=None,
            audience={"label": audience, "user_ids": list(range(1, min(cnt, 20) + 1))},
            deadline_at=deadline, status=status, created_by=1,
        ))

    # 培训分配（对应员工三态：completed/progress/none）
    assign_rows = [
        (1, 1, 1, "completed"), (2, 2, 5, "progress"),
        (3, 1, 1, "completed"), (5, 2, 5, "progress"),
        (8, 1, 1, "progress"),
    ]
    for uid, task_id, course_id, train in assign_rows:
        db.add(TrainingAssignment(
            task_id=task_id, course_id=course_id,
            user_id=uid, progress=100 if train == "completed" else 60,
            status="completed" if train == "completed" else "learning",
            completed_at=NOW - timedelta(days=3) if train == "completed" else None,
        ))

    questions = [
        (1, "single", "收到一封来自\"HR@company.com\"的邮件，要求点击链接更新工资卡信息，最合理的做法是？",
         ["A.直接点击链接", "B.回复邮件确认", "C.通过企业微信找HR核实", "D.转发给同事"], "C", 1, 2),
        (2, "multi", "以下哪些属于常见的钓鱼攻击手法？（多选）",
         ["仿冒OA登录页", "伪造快递签收短信", "正常会议邀请"], "A,B", 2, 3),
        (3, "judge", "邮件中只要有公司logo和发件人域名正确，就可以放心点击链接。", [], "B", 1, 1),
        (4, "single", "在公共场合发现写有\"工资单\"字样的U盘，正确做法是？",
         ["A.插入电脑查看", "B.带回家再看", "C.交给IT部门处理", "D.丢到垃圾桶"], "C", 2, 4),
        (5, "multi", "发现可疑邮件后，可以采取以下哪些正确措施？",
         ["点击举报按钮", "转发给IT安全团队", "直接回复询问发件人"], "A,B", 3, 3),
        (6, "judge", "为了方便记忆，可以将多个系统的密码设置为同一个强密码。", [], "B", 2, 1),
        (7, "single", "收到要求紧急转账的\"财务总监\"微信消息，应该？",
         ["A.立即转账", "B.电话或当面确认", "C.回复确认账号", "D.先转一半"], "B", 3, 5),
    ]
    for qid, qtype, content, options, answer, diff, course_id in questions:
        db.add(ExamQuestion(
            id=qid, type=qtype, content=content, options=options, answer=answer,
            analysis="", difficulty=diff, course_id=course_id, created_by=1,
        ))

    papers = [
        (1, "Q3全员信息安全摸底考试", 80, 3),
        (2, "财务人员专项测评（高级）", 75, 2),
        (3, "新员工入职安全结业考试", 70, 5),
        (4, "钓鱼邮件识别月度考核", 80, 4),
        (5, "高管合规专项试卷", 85, 1),
    ]
    for pid, title, pass_score, publish in papers:
        db.add(ExamPaper(id=pid, title=title, pass_score=pass_score, duration_min=30,
                         status="published", created_by=1))
        for qid in [1, 2, 3, 4, 5][:3 + pid % 3]:
            db.add(ExamPaperQuestion(paper_id=pid, question_id=qid, score=5))
        for i in range(publish):
            db.add(ExamRecord(
                paper_id=pid, user_id=i + 1, score=pass_score + (i % 3) * 5,
                passed=1, submitted_at=NOW - timedelta(days=i),
            ))
    db.flush()


def seed_analytics(db):
    """8. 分析：stat_daily 平台周/部门/场景行。"""
    # 平台：本月 4 周（中招人数 142/187/121/96，中招率 21.4/19.6/16.2/13.1）
    weekly = [
        (142, Decimal("21.4")), (187, Decimal("19.6")), (121, Decimal("16.2")), (96, Decimal("13.1")),
    ]
    for i, (victims, rate) in enumerate(weekly):
        targets = int(victims / rate * 100)
        db.add(StatDaily(
            stat_date=TODAY - timedelta(days=(3 - i) * 7), dim_type="platform",
            campaign_cnt=3, target_cnt=targets, delivered_cnt=targets,
            open_cnt=int(targets * 0.71), click_cnt=int(targets * 0.27),
            submit_cnt=victims, report_cnt=int(targets * 0.22),
        ))
    # 部门行（8 部门中招率）
    dept_rates = [(2, 9), (3, 32), (4, 17), (5, 26), (6, 21), (7, 11), (8, 9), (10, 32), (11, 31)]
    for dept_id, rate in dept_rates:
        targets = 200 + dept_id * 40
        db.add(StatDaily(
            stat_date=TODAY - timedelta(days=2), dim_type="dept", dim_id=dept_id,
            campaign_cnt=2, target_cnt=targets, delivered_cnt=targets,
            open_cnt=int(targets * 0.7), click_cnt=int(targets * 0.3),
            submit_cnt=int(targets * rate / 100), report_cnt=int(targets * 0.1),
        ))
    # 场景行
    scenes = [("finance", 36), ("hr", 22), ("system", 19), ("lottery", 26), ("holiday", 16)]
    for key, rate in scenes:
        targets = 300
        db.add(StatDaily(
            stat_date=TODAY - timedelta(days=3), dim_type="scene", dim_key=key,
            campaign_cnt=1, target_cnt=targets, delivered_cnt=targets,
            open_cnt=int(targets * 0.72), click_cnt=int(targets * 0.3),
            submit_cnt=int(targets * rate / 100), report_cnt=int(targets * 0.09),
        ))
    db.flush()


def seed_report(db):
    """9. 举报：8 条举报 + 奖励日志。"""
    rows = [
        ("【紧急】8月工资条更新，请核对银行账户", "hr-notice@phishing-shop.com", 11, "real_phishing", "manual"),
        ("Q3全员防钓鱼演练 - 财务报销提醒", "caiwu@drill-domain.com", 4, "drill", "manual"),
        ("Re: 项目例会纪要（8月15日）", "project-team@example.com", 1, "false_positive", "manual"),
        ("Fedex 快递签收通知 - 运单号77889922", "fedex-express@service-alert.cc", 5, "real_phishing", "manual"),
        ("【VPN续费】账号即将冻结，请点击完成验证", "it-support@company-verification.top", 12, "real_phishing", "manual"),
        ("报销审批通过 - 单据 #BZ20260814-0028", "workflow@example.com", 8, "false_positive", "manual"),
        ("Q3演练-会议日程变更，请更新日历", "it@drill-domain.com", 3, "drill", "auto"),
        ("【重要】Google Drive 文件共享 - 员工手册 v3", "drive-shared@doc-share.xyz", 9, "real_phishing", "auto"),
    ]
    for i, (subject, sender, uid, classification, classifier) in enumerate(rows):
        db.add(MailReport(
            id=i + 1, channel="outlook_plugin", reporter_user_id=uid,
            reporter_email=f"user{uid}@jianfa.com",
            from_addr=sender, subject=subject,
            classification=classification, classifier=classifier,
            matched_campaign_id=1 if classification == "drill" else None,
            handler_id=1 if classifier == "manual" else None,
            handled_at=NOW - timedelta(hours=i) if classifier == "manual" else None,
            reward_points=10 if classification == "drill" else (20 if classification == "real_phishing" else 0),
        ))
    db.add(ReportRewardLog(user_id=4, report_id=2, points=10, reason="演练邮件举报"))
    db.add(ReportRewardLog(user_id=11, report_id=1, points=20, reason="真实钓鱼举报"))
    db.flush()


def seed_system(db):
    """10. 系统：参数、webhook、siem、审计、登录日志、开放平台、AI。"""
    settings_kv = [
        ("name", "企业防钓鱼演练平台"),
        ("copyright", "© 2026 公司信息安全部 版权所有"),
        ("icp", "京ICP备2026000000号-1"),
        ("pixel_enabled", "1"),
        ("track_domain", "track.drill-domain.com"),
        ("drill_domain", "drill.phishlab.cn"),
        ("link_expire", "campaign"),
        ("redirect_url", "https://company.com"),
        ("retention_days", "180"),
        ("disclaimer", "本平台所有钓鱼演练活动仅用于企业内部安全意识教育目的。"),
        ("ai_switches", '{"chat":true,"template":true,"analysis":true,"recommend":false}'),
        ("compliance_confirm", "1"),
    ]
    for key, value in settings_kv:
        db.add(PlatformSetting(setting_key=key, setting_value=value, updated_by=1))

    db.add(WebhookConfig(
        id=1, name="企业微信告警", im_type="wecom",
        url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=demo",
        event_types=["campaign_done", "high_risk", "new_real_phish"], enabled=1,
    ))
    db.add(WebhookConfig(
        id=2, name="钉钉告警", im_type="dingtalk",
        url="https://oapi.dingtalk.com/robot/send?access_token=demo",
        event_types=["high_risk"], enabled=0,
    ))
    db.add(SiemConfig(
        id=1, host="siem.corp.local", port=514, protocol="udp", format="cef",
        event_types=["campaign_start", "submit", "report"], enabled=1,
    ))

    for i, (name, action, target, ip) in enumerate([
        ("超级管理员", "campaign:create", "Q3全员防钓鱼演练", "10.0.1.22"),
        ("超级管理员", "template:create", "【财务通知】报销截止提醒", "10.0.1.22"),
        ("超级管理员", "channel:create", "备用SMTP服务器", "10.0.1.22"),
        ("超级管理员", "settings:update", "数据留存周期 90天 → 180天", "10.0.1.22"),
        ("超级管理员", "org:create_user", "EMP020 许静", "10.0.1.22"),
    ]):
        db.add(AuditLog(
            id=i + 1, account_id=1, account_name=name, module=action.split(":")[0],
            action=action.split(":")[1], target_type="演示", target_id=target,
            detail={"demo": True}, ip=ip,
        ))
    for i, (user, ip, ua, ok) in enumerate([
        ("admin", "10.0.1.22", "Chrome 125 · Windows 10", 1),
        ("admin", "10.0.1.22", "Edge 125 · Windows 11", 1),
        ("unknown", "202.108.x.x", "Chrome 120 · macOS", 0),
        ("admin", "10.0.1.22", "Safari 17 · macOS 14", 1),
        ("admin", "10.0.1.22", "Safari 17 · macOS 14", 0),
    ]):
        db.add(LoginLog(
            id=i + 1, account_id=1, username=user, login_type="local",
            success=ok, fail_reason=None if ok else "密码错误", ip=ip, ua=ua,
        ))

    # 开放平台应用
    for i, (name, scopes) in enumerate([
        ("安全运营自动化", ["campaign", "report"]),
        ("HR 系统集成", ["user"]),
        ("报表导出工具", ["report", "system"]),
    ]):
        app = OpenApp(
            id=i + 1, app_id=f"app_{i + 1:08x}", name=name,
            app_secret_enc=encrypt_secret(f"sk_live_demo{i + 1}" + "a" * 20),
            scopes=scopes, ip_whitelist=[], rate_limit=60, status="active",
            created_by=1, description=f"{name} 演示应用",
        )
        db.add(app)
        for j in range(2):
            db.add(OpenApiLog(
                app_id=app.app_id, method="GET", path="/openapi/v1/campaigns",
                status_code=200, latency_ms=40 + j * 15, ip="10.0.3.10",
            ))

    db.add(AiProvider(
        id=1, name="本地演示引擎", type="local", model="local-demo",
        temperature=Decimal("0.70"), max_tokens=2048, enabled=1, data_outbound=0,
    ))
    s1 = AiSession(id=1, account_id=1, title="分析最近一次演练效果", page_context={"route": "/dashboard"})
    s2 = AiSession(id=2, account_id=1, title="生成财务类钓鱼邮件模板", page_context={"route": "/template"})
    db.add(s1)
    db.add(s2)
    db.flush()
    db.add(AiMessage(session_id=1, role="user", content="帮我分析最近一次演练效果"))
    db.add(AiMessage(session_id=1, role="assistant", content="累计演练目标 8,238 人，平均中招率 16.9%。"))
    db.add(AiMessage(session_id=2, role="user", content="生成一封财务报销主题的钓鱼模板"))
    db.add(AiMessage(session_id=2, role="assistant", content="已生成草稿，请在「AI模板生成」页查看并确认入库。"))

    db.add(AiDraft(
        id=1, biz_type="email_template", title="【财务通知】报销单待处理",
        content='{"name":"财务报销·AI生成模板","scene":"finance","subject":"【财务通知】报销单待处理","body":"<div>{{{.FirstName}}}，您好：请点击链接处理。</div>"}',
        status="draft", created_by=1,
    ))
    db.add(AiDraft(
        id=2, biz_type="report_summary", title="Q3演练效果分析（演示）",
        content="# 演练效果分析\n\n平均中招率 15.6%。", status="approved",
        created_by=1, reviewer_id=1, reviewed_at=NOW - timedelta(days=1),
    ))
    db.flush()


def main():
    db = SessionLocal()
    try:
        print("清空业务表…")
        for t in TRUNCATE_TABLES:
            db.execute(text(f"DELETE FROM {t}"))
        db.commit()
        print("写入种子数据…")
        seed_rbac(db)
        seed_org(db)
        seed_license(db)
        seed_template(db)
        seed_channel(db)
        seed_campaign(db)
        seed_training(db)
        seed_analytics(db)
        seed_report(db)
        seed_system(db)
        db.commit()
        print("完成：admin / PhishLab@2026")
    finally:
        db.close()


if __name__ == "__main__":
    main()
