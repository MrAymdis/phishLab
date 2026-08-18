"""组织与员工服务：部门树、员工档案 CRUD、风险画像、分组标签、组织同步。"""
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.deps import apply_data_scope
from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret, encrypt_secret
from app.modules.campaign.models import Campaign
from app.modules.tracking.models import TrackEvent
from app.modules.training.models import TrainingAssignment

from .models import (
    EmpDept, EmpGroup, EmpGroupMember, EmpRiskProfile, EmpTag, EmpUser, EmpUserTag,
)

# 头像底色盘（与前端 UsersView avatarColors 一致）
_AVATAR_COLORS = ["#378ADD", "#1D9E75", "#7F77DD", "#EF9F27", "#D85A30", "#0D9488"]
_RISK_CODE = {1: "low", 2: "mid", 3: "high"}
# 五维初始分偏移（基于 initial_risk）
_DIM_OFFSETS = (-10, 15, 25, 5, -20)
_DIM_DEFS = [
    ("email_recognize", "邮件识别"),
    ("link_click", "链接点击"),
    ("pwd_submit", "密码提交"),
    ("attach_run", "附件下载"),
    ("report_awareness", "举报意识"),
]
# 轨迹事件 → (时间轴样式, 文案)
_EVENT_STYLE = {
    "submit": ("danger", "中招 · 提交数据"),
    "open": ("warning", "打开了邮件"),
    "click": ("primary", "点击了链接"),
    "report": ("success", "主动举报"),
}
_FMT = "%Y-%m-%d %H:%M:%S"


# ---------- 通用辅助 ----------

def _risk_level_of(score: int) -> int:
    """风险分 → 等级：1低(0-70) 2中(71-80) 3高(81-100)。"""
    if score <= 70:
        return 1
    if score <= 80:
        return 2
    return 3


def _total_from_dims(email: int, link: int, pwd: int, attach: int, awareness: int) -> int:
    """综合评分 = 五维风险均值（举报意识为反向指标：风险贡献 = 100 - 意识分）。"""
    risk_aware = max(0, 100 - awareness)
    return max(0, min(100, round((email + link + pwd + attach + risk_aware) / 5)))


def _mask_mobile(mobile_enc: bytes | None) -> str:
    """手机号掩码：前3 + **** + 后4；无值/解密失败返回空串。"""
    if not mobile_enc:
        return ""
    try:
        plain = decrypt_secret(mobile_enc)
    except Exception:
        return ""
    if len(plain) < 8:
        return plain[:1] + "****"
    return plain[:3] + "****" + plain[-4:]


def _load_dept_map(db: Session) -> dict[int, EmpDept]:
    return {d.id: d for d in db.scalars(select(EmpDept)).all()}


def _dept_names(dept: EmpDept | None, dept_map: dict[int, EmpDept]) -> list[str]:
    """按 emp_dept.path 展开部门名链（含自身），如 总公司/技术部/研发组。"""
    if dept is None:
        return []
    names = []
    for part in dept.path.strip("/").split("/"):
        if part and int(part) in dept_map:
            names.append(dept_map[int(part)].name)
    if not names:  # path 异常兜底
        names.append(dept.name)
    return names


def _user_rows(db: Session, users: list[EmpUser], dept_map: dict[int, EmpDept]) -> list[dict]:
    """批量组装员工行：标签/风险画像/培训状态各一次查询。"""
    ids = [u.id for u in users]

    tags_map: dict[int, list[str]] = {}
    for uid, name in db.execute(
        select(EmpUserTag.user_id, EmpTag.name)
        .join(EmpTag, EmpTag.id == EmpUserTag.tag_id)
        .where(EmpUserTag.user_id.in_(ids))
    ).all():
        tags_map.setdefault(uid, []).append(name)

    profiles = {p.user_id: p for p in db.scalars(
        select(EmpRiskProfile).where(EmpRiskProfile.user_id.in_(ids))
    ).all()}

    # 培训状态：任一 completed → completed；否则任一 learning/pending → progress；否则 none
    train_map: dict[int, str] = {}
    for uid, status in db.execute(
        select(TrainingAssignment.user_id, TrainingAssignment.status)
        .where(TrainingAssignment.user_id.in_(ids))
    ).all():
        cur = train_map.get(uid)
        if status == "completed":
            train_map[uid] = "completed"
        elif cur != "completed" and status in ("learning", "pending"):
            train_map[uid] = "progress"

    rows = []
    for u in users:
        profile = profiles.get(u.id)
        names = _dept_names(dept_map.get(u.dept_id), dept_map)
        rows.append({
            "id": u.id,
            "name": u.name,
            "no": u.emp_no or "",
            "dept": " / ".join(names),
            "deptShort": names[-1] if names else "",
            "pos": u.position or "",
            "email": u.email,
            "phone": _mask_mobile(u.mobile_enc),
            "risk": _RISK_CODE.get(profile.risk_level if profile else 1, "low"),
            "riskScore": int(profile.total_score) if profile else 70,
            "tags": tags_map.get(u.id, []),
            "clicks": int(profile.phish_count) if profile else 0,
            "training": train_map.get(u.id, "none"),
            "avatarColor": _AVATAR_COLORS[u.id % len(_AVATAR_COLORS)],
        })
    return rows


# ---------- 部门 ----------

def dept_tree(db: Session, account) -> list[dict]:
    """部门树（人数含子部门累计，children 按 sort 排序）。"""
    depts = db.scalars(select(EmpDept).order_by(EmpDept.sort, EmpDept.id)).all()
    direct = dict(db.execute(
        select(EmpUser.dept_id, func.count(EmpUser.id))
        .where(EmpUser.status == 1)
        .group_by(EmpUser.dept_id)
    ).all())
    # 部门人数 = 自身 + 所有 path 前缀命中的子部门
    id_to_dept = {d.id: d for d in depts}
    total = {
        d.id: sum(cnt for did, cnt in direct.items()
                  if id_to_dept.get(did) and id_to_dept[did].path.startswith(d.path))
        for d in depts
    }
    nodes = {d.id: {"id": d.id, "label": d.name, "count": total[d.id], "children": []} for d in depts}
    roots = []
    for d in depts:  # 已按 sort,id 有序，append 后 children 天然有序
        node = nodes[d.id]
        if d.parent_id and d.parent_id in nodes:
            nodes[d.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_dept(db: Session, account, payload: dict) -> int:
    """新增部门：校验父部门，path 继承父级 + 自身 id。"""
    parent_id = int(payload.get("parent_id") or 0)
    parent = None
    if parent_id > 0:
        parent = db.get(EmpDept, parent_id)
        if parent is None:
            raise BizError(ErrorCode.PARAM_INVALID, "上级部门不存在")
    dept = EmpDept(
        parent_id=parent_id,
        path=(parent.path if parent else "/"),  # 占位：path NOT NULL，flush 后补全
        name=payload["name"],
        code=payload.get("code"),
        sort=0,
        source="manual",
    )
    db.add(dept)
    db.flush()  # 取自增 id 后补全 path
    dept.path = (parent.path if parent else "/") + f"{dept.id}/"
    db.commit()
    record_audit(
        db, account=account, module="org", action="create_dept",
        target_type="emp_dept", target_id=str(dept.id),
        detail={"name": dept.name, "parent_id": parent_id},
    )
    return dept.id


def sync_org(db: Session, account, source: str) -> dict:
    """触发组织架构同步（LDAP/企微/钉钉/飞书）。真实拉取比对 TODO(二期)。"""
    record_audit(db, account=account, module="org", action="sync_org", detail={"source": source})
    return {"status": "queued", "source": source}


# ---------- 员工 ----------

def list_users(db: Session, account, *, dept_id=None, tag=None, risk_level=None,
               kw=None, page=1, page_size=20) -> dict:
    """员工档案列表：手机掩码，数据权限过滤（含子部门/标签/风险/关键字）。"""
    stmt = apply_data_scope(
        db, select(EmpUser).where(EmpUser.status == 1), account, dept_col=EmpUser.dept_id,
    )
    if dept_id:
        dept = db.get(EmpDept, dept_id)
        if dept:
            # 命中自身及所有子部门（path 前缀匹配）
            dept_ids = [d.id for d in db.scalars(
                select(EmpDept).where(EmpDept.path.like(f"{dept.path}%"))
            ).all()]
            dept_ids.append(dept.id)
            stmt = stmt.where(EmpUser.dept_id.in_(dept_ids))
    if tag:
        stmt = stmt.where(EmpUser.id.in_(
            select(EmpUserTag.user_id)
            .join(EmpTag, EmpTag.id == EmpUserTag.tag_id)
            .where(EmpTag.name == tag)
        ))
    if risk_level:
        stmt = stmt.where(EmpUser.id.in_(
            select(EmpRiskProfile.user_id).where(EmpRiskProfile.risk_level == risk_level)
        ))
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(or_(
            EmpUser.name.like(like), EmpUser.emp_no.like(like), EmpUser.email.like(like),
        ))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(
        stmt.order_by(EmpUser.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    rows = _user_rows(db, users, _load_dept_map(db))
    return {"list": rows, "total": total, "page": page, "pageSize": page_size}


def _bind_tags(db: Session, user_id: int, tag_ids: list[int]) -> None:
    """重绑标签（先删后插），仅绑定存在的标签。"""
    db.execute(delete(EmpUserTag).where(EmpUserTag.user_id == user_id))
    valid = set(db.scalars(
        select(EmpTag.id).where(EmpTag.id.in_(tag_ids or []))
    ).all())
    for tid in valid:
        db.add(EmpUserTag(user_id=user_id, tag_id=tid))


def create_user(db: Session, account, payload: dict) -> int:
    """新增员工：手机 encrypt_secret 入库；初始化风险画像（五维带偏移）与标签。"""
    email = payload["email"]
    if db.scalar(select(EmpUser.id).where(EmpUser.email == email, EmpUser.status == 1)):
        raise BizError(ErrorCode.PARAM_INVALID, "邮箱已存在")
    user = EmpUser(
        emp_no=payload.get("emp_no"),
        name=payload["name"],
        email=email,
        mobile_enc=encrypt_secret(payload["mobile"]) if payload.get("mobile") else None,
        dept_id=payload["dept_id"],
        position=payload.get("position"),
        source="manual",
    )
    db.add(user)
    db.flush()  # 取自增 id

    initial = min(max(int(payload.get("initial_risk") or 70), 0), 100)
    user.initial_risk = initial
    dims = [min(max(initial + off, 0), 100) for off in _DIM_OFFSETS]
    total = _total_from_dims(*dims)
    db.add(EmpRiskProfile(
        user_id=user.id,
        total_score=total,
        email_recognize=dims[0],
        link_click=dims[1],
        pwd_submit=dims[2],
        attach_run=dims[3],
        report_awareness=dims[4],
        risk_level=_risk_level_of(total),
    ))
    _bind_tags(db, user.id, payload.get("tag_ids") or [])
    db.commit()
    record_audit(
        db, account=account, module="org", action="create_user",
        target_type="emp_user", target_id=str(user.id),
        detail={"email": email, "dept_id": user.dept_id},
    )
    return user.id


def get_user(db: Session, account, user_id: int) -> dict:
    """员工档案详情：列表行 + 初始风险/来源/状态/创建时间。"""
    user = db.get(EmpUser, user_id)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    row = _user_rows(db, [user], _load_dept_map(db))[0]
    row.update({
        "initial_risk": user.initial_risk,
        "source": user.source,
        "status": user.status,
        "created_at": user.created_at.strftime(_FMT) if user.created_at else "",
    })
    return row


def update_user(db: Session, account, user_id: int, payload: dict) -> dict:
    """编辑员工：改字段（邮箱唯一性排除自身）、重绑标签、initial_risk 变更时同步画像。"""
    user = db.get(EmpUser, user_id)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    email = payload["email"]
    if db.scalar(select(EmpUser.id).where(EmpUser.email == email, EmpUser.id != user_id, EmpUser.status == 1)):
        raise BizError(ErrorCode.PARAM_INVALID, "邮箱已存在")

    user.name = payload["name"]
    user.email = email
    user.emp_no = payload.get("emp_no")
    user.dept_id = payload["dept_id"]
    user.position = payload.get("position")
    if payload.get("mobile"):
        user.mobile_enc = encrypt_secret(payload["mobile"])
    elif payload.get("mobile") == "":
        user.mobile_enc = None

    _bind_tags(db, user.id, payload.get("tag_ids") or [])

    initial = payload.get("initial_risk")
    if initial is not None and int(initial) != user.initial_risk:
        user.initial_risk = min(max(int(initial), 0), 100)
        profile = db.get(EmpRiskProfile, user.id)
        if profile is None:
            profile = EmpRiskProfile(user_id=user.id)
            db.add(profile)
        dims = [min(max(user.initial_risk + off, 0), 100) for off in _DIM_OFFSETS]
        profile.email_recognize, profile.link_click = dims[0], dims[1]
        profile.pwd_submit, profile.attach_run = dims[2], dims[3]
        profile.report_awareness = dims[4]
        profile.total_score = _total_from_dims(*dims)
        profile.risk_level = _risk_level_of(profile.total_score)
    db.commit()
    record_audit(
        db, account=account, module="org", action="update_user",
        target_type="emp_user", target_id=str(user.id),
        detail={"email": email, "dept_id": user.dept_id},
    )
    return get_user(db, account, user_id)


def delete_user(db: Session, account, user_id: int) -> dict:
    """软删除：status=0 离职停用，不物理删除。"""
    user = db.get(EmpUser, user_id)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    user.status = 0
    db.commit()
    record_audit(
        db, account=account, module="org", action="delete_user",
        target_type="emp_user", target_id=str(user.id),
        detail={"email": user.email},
    )
    return {"id": user_id}


def import_users_csv(db: Session, account, content: bytes) -> dict:
    """CSV 批量导入：工号,姓名,邮箱[,部门,岗位,手机号,初始风险]；逐行容错。

    部门按名称精确匹配或「技术部/研发组」路径逐级匹配；不匹配的行跳过并返回原因。
    """
    import csv
    import io
    import re

    text = content.decode("utf-8-sig", errors="ignore")
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except Exception:
        raise BizError(ErrorCode.PARAM_INVALID, "CSV 解析失败，请检查文件格式")
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        raise BizError(ErrorCode.PARAM_INVALID, "CSV 内容为空")

    # 表头识别：首行含「邮箱/email」视为表头
    header = [ (h or "").strip() for h in rows[0] ]
    has_header = any("邮箱" in h or "email" in h.lower() for h in header)
    data_rows = rows[1:] if has_header else rows

    def col_idx(names):
        for n in names:
            for i, h in enumerate(header):
                if n in h or h in n:
                    return i
        return None

    if has_header:
        idx_no = col_idx(("工号", "员工编号", "no"))
        idx_name = col_idx(("姓名", "name"))
        idx_email = col_idx(("邮箱", "email"))
        idx_dept = col_idx(("部门", "dept"))
        idx_pos = col_idx(("岗位", "职位", "position"))
        idx_mobile = col_idx(("手机", "电话", "mobile", "phone"))
        idx_risk = col_idx(("初始风险", "风险", "risk"))
        idx_tags = col_idx(("标签", "tag"))
    else:
        # 无表头：固定顺序 工号,姓名,邮箱,部门,岗位,手机号,初始风险,标签
        idx_no, idx_name, idx_email, idx_dept, idx_pos, idx_mobile, idx_risk, idx_tags = 0, 1, 2, 3, 4, 5, 6, 7

    def cell(row, idx):
        if idx is None or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    dept_cache: dict[str, int | None] = {}

    def resolve_dept(name: str) -> int | None:
        if not name:
            return None
        if name in dept_cache:
            return dept_cache[name]
        d = db.scalar(select(EmpDept).where(EmpDept.name == name))
        if d is not None:
            dept_cache[name] = d.id
            return d.id
        # 路径匹配：「技术部/研发组」按名称路径比对（兼容有无根节点前缀与两种分隔符）
        normalized = name.replace(" / ", "/")
        nodes = list(db.scalars(select(EmpDept)).all())
        by_id = {n.id: n for n in nodes}

        def path_of(n):
            parts = [n.name]
            while n.parent_id and n.parent_id in by_id:
                n = by_id[n.parent_id]
                parts.append(n.name)
            return "/".join(reversed(parts))

        for n in nodes:
            full = path_of(n)
            if full == normalized:
                dept_cache[name] = n.id
                return n.id
        # 去除根节点前缀后再比一次（总公司/技术部/研发组 → 技术部/研发组）
        for n in nodes:
            full = path_of(n)
            parts = full.split("/")
            if len(parts) > 1 and "/".join(parts[1:]) == normalized:
                dept_cache[name] = n.id
                return n.id
        dept_cache[name] = None
        return None

    imported = 0
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(data_rows):
        line_no = i + 2 if has_header else i + 1
        name = cell(row, idx_name)
        email = cell(row, idx_email)
        if not name or not email:
            errors.append(f"第{line_no}行：姓名/邮箱不能为空")
            continue
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            errors.append(f"第{line_no}行：邮箱格式不正确（{email}）")
            continue
        if email in seen or db.scalar(select(EmpUser.id).where(EmpUser.email == email, EmpUser.status == 1)):
            errors.append(f"第{line_no}行：邮箱已存在（{email}）")
            continue
        seen.add(email)
        dept_name = cell(row, idx_dept)
        dept_id = resolve_dept(dept_name)
        if dept_name and dept_id is None:
            errors.append(f"第{line_no}行：部门不存在（{dept_name}）")
            continue
        if dept_id is None:
            dept_id = db.scalar(select(EmpDept.id).where(EmpDept.parent_id == 0).order_by(EmpDept.id).limit(1)) or 0
        try:
            risk = int(cell(row, idx_risk)) if cell(row, idx_risk) else 70
        except ValueError:
            risk = 50
        # 标签：逗号/分号分隔的标签名，按名解析，不存在的自动创建
        tag_names = [t.strip() for t in re.split(r"[,，;；]", cell(row, idx_tags)) if t.strip()]
        tag_ids: list[int] = []
        for tn in tag_names:
            tag = db.scalar(select(EmpTag).where(EmpTag.name == tn))
            if tag is None:
                tag = EmpTag(name=tn, color=None)
                db.add(tag)
                db.flush()
            tag_ids.append(tag.id)
        create_user(db, account, {
            "emp_no": cell(row, idx_no) or None,
            "name": name,
            "email": email,
            "mobile": cell(row, idx_mobile) or None,
            "dept_id": dept_id or 0,
            "position": cell(row, idx_pos) or None,
            "tag_ids": tag_ids,
            "initial_risk": risk,
        })
        imported += 1

    record_audit(
        db, account=account, module="org", action="import_users_csv",
        target_type="emp_user", target_id=None,
        detail={"imported": imported, "failed": len(errors)},
    )
    return {"imported": imported, "failed": len(errors), "errors": errors[:20]}


# ---------- 风险画像 ----------

def _dim_color(val: int) -> str:
    if val > 70:
        return "#f56c6c"
    if val > 40:
        return "#e6a23c"
    return "#67c23a"


def _risk_history(db: Session, user_id: int) -> list[dict]:
    """最近 8 条演练行为轨迹（track_event join campaign）。"""
    rows = db.execute(
        select(TrackEvent.event_type, TrackEvent.created_at, Campaign.name)
        .join(Campaign, Campaign.id == TrackEvent.campaign_id)
        .where(
            TrackEvent.user_id == user_id,
            TrackEvent.event_type.in_(["submit", "open", "click", "report"]),
        )
        .order_by(TrackEvent.created_at.desc())
        .limit(8)
    ).all()
    history = []
    for event_type, created_at, campaign_name in rows:
        style, copy = _EVENT_STYLE.get(event_type, ("primary", "触发演练追踪"))
        time_str = created_at.strftime(_FMT) if created_at else ""
        history.append({
            "time": time_str,
            "type": style,
            "title": f"演练「{campaign_name or ''}」",
            "desc": f"{copy} · {time_str}",
        })
    return history


def get_risk_profile(db: Session, account, user_id: int) -> dict:
    """五维雷达 + 最近行为轨迹；无画像时返回默认值。"""
    if db.get(EmpUser, user_id) is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    profile = db.get(EmpRiskProfile, user_id)
    if profile is None:
        dims = [{"label": label, "val": 70, "color": _dim_color(70)} for _, label in _DIM_DEFS]
        total, risk_level, phish, report, training_completion = 70, 1, 0, 0, 0.0
    else:
        dims = [
            {"label": label, "val": int(getattr(profile, attr)), "color": _dim_color(int(getattr(profile, attr)))}
            for attr, label in _DIM_DEFS
        ]
        total = int(profile.total_score)
        risk_level = int(profile.risk_level)
        phish = int(profile.phish_count)
        report = int(profile.report_count)
        training_completion = float(profile.training_completion or 0)
    return {
        "dims": dims,
        "total": total,
        "riskLevel": risk_level,
        "phishCount": phish,
        "reportCount": report,
        "trainingCompletion": training_completion,
        "history": _risk_history(db, user_id),
    }


# ---------- 分组 / 标签 ----------

def list_groups(db: Session, account) -> list[dict]:
    rows = db.execute(
        select(EmpGroup, func.count(EmpGroupMember.user_id))
        .outerjoin(EmpGroupMember, EmpGroupMember.group_id == EmpGroup.id)
        .group_by(EmpGroup.id)
        .order_by(EmpGroup.id)
    ).all()
    return [
        {"id": g.id, "name": g.name, "user_count": int(cnt), "remark": g.remark or ""}
        for g, cnt in rows
    ]


def list_tags(db: Session, account) -> list[dict]:
    rows = db.execute(
        select(EmpTag, func.count(EmpUserTag.user_id))
        .outerjoin(EmpUserTag, EmpUserTag.tag_id == EmpTag.id)
        .group_by(EmpTag.id)
        .order_by(EmpTag.id)
    ).all()
    return [
        {"id": t.id, "name": t.name, "color": t.color or "", "user_count": int(cnt)}
        for t, cnt in rows
    ]


def create_tag(db: Session, account, payload: dict) -> int:
    """创建标签：名称唯一校验 + 审计。"""
    name = (payload.get("name") or "").strip()
    if not name:
        raise BizError(ErrorCode.PARAM_INVALID, "标签名称不能为空")
    exists = db.scalar(select(EmpTag).where(EmpTag.name == name))
    if exists:
        raise BizError(ErrorCode.PARAM_INVALID, f"标签「{name}」已存在")
    tag = EmpTag(name=name, color=payload.get("color") or None)
    db.add(tag)
    db.commit()
    record_audit(
        db, account=account, module="org", action="create_tag",
        target_type="emp_tag", target_id=str(tag.id), detail={"name": name},
    )
    return tag.id
