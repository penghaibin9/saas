"""旧业务域「影子学生台账」的统一约束与双读（学生主档统一整改 阶段 D）。

背景：在校服务、旧学业、就业三个域各自有一张学生台账表（CsServiceStudent /
AcademicStudent / EmpStudent），历史上都能脱离 StudentProfile 独立新增，于是同一个人
在系统里出现四份互不相干的「学生」，改了学籍其它域看不到、查数对不上、越权范围算不准。

阶段 D 的止血口径：

1. **不再产生无主档的影子行**。三个域的新增一律要求该学生的学籍档案已存在
   （传 studentId 或用学号能唯一命中主档），否则报 DEPRECATED_WRITE_PATH，
   提示先到教务/系统管理建学籍。迎新是例外，候选人本来就还不是学生，保留原语义。
2. **身份字段以主档为准**。新增时身份字段从主档快照，不采信调用方传值；
   已绑定行的姓名/学号/组织不允许在业务域改，只能走学籍更正。
3. **读取双读**。已绑定行展示主档当前身份（改了学籍这里立刻跟着变）；
   未回填的历史行继续用自己的快照，并在响应里标 legacyFallback=true，
   让前端和运维一眼看出「这条还没接上主档」。

写入侧不做兜底：宁可让调用方看到明确错误，也不要再悄悄造一个影子学生。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException

# 无主档新增被拒时的业务码。410 Gone：这条写路径已下线，不是参数错、也不是没权限。
DEPRECATED_WRITE_PATH = "DEPRECATED_WRITE_PATH"

# 各域新增被拒时告诉用户该去哪儿建档
_ENTRY_HINT = "请先在「教务中心 → 学籍导入/补录」或「系统管理 → 学生导入与账号开通」建立学籍档案，再回本页创建业务记录"


def reject_free_form_create(domain_label: str, key_label: str = "学号") -> None:
    """无法定位主档时统一拒绝。"""
    raise AppException(
        DEPRECATED_WRITE_PATH,
        f"{domain_label}不能独立新增学生：该{key_label}在学籍档案里查不到。{_ENTRY_HINT}",
        http_status=410)


def resolve_profile_for_shadow(db, tenant_id: int, *, domain_label: str,
                               student_id=None, student_no: str | None = None):
    """定位业务记录应绑定的学籍档案；定位不到直接拒绝新增。

    优先用显式 studentId（前端从学籍选人时应当传它），退而用学号唯一匹配。
    学号命中多条（历史脏数据）也拒绝——让人先把主档理干净，别再叠一层影子。
    """
    from app.models import StudentProfile

    if student_id not in (None, "", 0, "0"):
        try:
            sid = int(student_id)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "studentId 须为数字")
        p = db.get(StudentProfile, sid)
        if not p or p.is_deleted or int(p.tenant_id) != int(tenant_id):
            raise AppException("VALIDATION_ERROR", "studentId 对应的学籍档案不存在或不属于本校")
        return p

    no = str(student_no or "").strip()
    if not no:
        reject_free_form_create(domain_label)
    rows = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == int(tenant_id),
        StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(False))).all()
    if not rows:
        reject_free_form_create(domain_label)
    if len(rows) > 1:
        raise AppException("DATA_CONFLICT",
                           f"学号 {no} 在学籍档案里存在 {len(rows)} 条记录，无法确定绑定哪一条，"
                           "请先在学籍管理处理重复档案")
    return rows[0]


def org_names(db, profile, cache: dict | None = None) -> tuple[str, str, str]:
    """主档组织 ID → (学院名, 专业名, 班级名)。cache 用于列表批量渲染避免逐行查。"""
    from app.models.org import College, Major, SchoolClass

    out = []
    for model, oid in ((College, profile.college_id), (Major, profile.major_id),
                       (SchoolClass, profile.class_id)):
        if not oid:
            out.append("")
            continue
        key = (model.__name__, int(oid))
        if cache is not None and key in cache:
            out.append(cache[key])
            continue
        row = db.get(model, oid)
        name = ""
        if row is not None:
            name = getattr(row, "college_name", None) or getattr(row, "major_name", None) \
                or getattr(row, "class_name", None) or ""
        if cache is not None:
            cache[key] = name
        out.append(name)
    return out[0], out[1], out[2]


def identity_snapshot(db, profile, cache: dict | None = None) -> dict:
    """建影子行时从主档取的身份快照（业务域不得自行编造这几项）。"""
    college_name, major_name, class_name = org_names(db, profile, cache)
    return {
        "student_id": int(profile.id),
        "name": profile.real_name,
        "student_no": profile.student_no,
        "gender": getattr(profile, "gender", None),
        "grade": getattr(profile, "grade", None),
        "college_name": college_name,
        "major_name": major_name,
        "class_id": str(profile.class_id) if profile.class_id else None,
        "class_name": class_name,
    }


def load_profiles(db, shadows) -> dict:
    """批量取回一批影子行绑定的主档 {profile_id: StudentProfile}（列表页消 N+1）。"""
    from app.models import StudentProfile

    ids = {int(s.student_id) for s in shadows if getattr(s, "student_id", None)}
    if not ids:
        return {}
    return {p.id: p for p in db.scalars(select(StudentProfile).where(
        StudentProfile.id.in_(ids))).all()}


def apply_dual_read(row: dict, shadow, profiles: dict, db=None, cache: dict | None = None) -> dict:
    """把一行影子渲染结果修正为「主档当前身份」，未绑定则标记 legacyFallback。

    row 由各域 `_stu_row` 生成后传入，就地覆写身份字段并补三个口径字段：
    - profileStudentId：绑定的学籍档案 id（未绑定为空字符串）
    - legacyFallback：true 表示本行还没接上主档，展示的是历史快照
    - identitySource：MASTER / LEGACY_SNAPSHOT，便于前端和排查区分
    """
    pid = getattr(shadow, "student_id", None)
    p = profiles.get(int(pid)) if pid else None
    if p is None or getattr(p, "is_deleted", False):
        row["profileStudentId"] = str(pid) if pid else ""
        row["legacyFallback"] = True
        row["identitySource"] = "LEGACY_SNAPSHOT"
        return row

    row["profileStudentId"] = str(p.id)
    row["legacyFallback"] = False
    row["identitySource"] = "MASTER"
    row["name"] = p.real_name
    row["studentNo"] = p.student_no or ""
    if getattr(p, "gender", None):
        row["gender"] = p.gender
    if getattr(p, "grade", None):
        row["grade"] = p.grade
    if db is not None:
        college_name, major_name, class_name = org_names(db, p, cache)
        if college_name:
            row["collegeName"] = college_name
        if major_name:
            row["majorName"] = major_name
        if class_name:
            row["className"] = class_name
        if p.class_id:
            row["classId"] = str(p.class_id)
    return row


_IDENTITY_FIELDS = ("name", "studentNo", "className", "collegeName", "majorName")


def assert_identity_immutable(db, shadow, body: dict, domain_label: str) -> None:
    """已绑定主档的行，禁止在业务域改身份字段。

    只有确实要改成"既不等于台账现值、也不等于主档现值"的内容时才报错：
    前端整表单回填会把只读的姓名一起提交回来，而页面显示的是双读后的主档姓名，
    若只跟台账存量比对，历史上没同步过的行会被误判成"想改名字"。
    """
    pid = getattr(shadow, "student_id", None)
    if not pid:
        return
    from app.models import StudentProfile

    p = db.get(StudentProfile, int(pid))
    accepted = {
        "name": {getattr(shadow, "name", None), getattr(p, "real_name", None)},
        "studentNo": {getattr(shadow, "student_no", None), getattr(p, "student_no", None)},
        "className": {getattr(shadow, "class_name", None)},
        "collegeName": {getattr(shadow, "college_name", None)},
        "majorName": {getattr(shadow, "major_name", None)},
    }
    if p is not None:
        c_name, m_name, k_name = org_names(db, p)
        accepted["className"].add(k_name)
        accepted["collegeName"].add(c_name)
        accepted["majorName"].add(m_name)

    changed = []
    for k in _IDENTITY_FIELDS:
        if body.get(k) is None:
            continue
        val = str(body[k]).strip()
        if val not in {str(x or "") for x in accepted[k]}:
            changed.append(k)
    if changed:
        raise AppException(
            "DEPRECATED_WRITE_PATH",
            f"该学生已绑定学籍档案，{domain_label}不能修改姓名/学号/组织等身份信息"
            f"（本次尝试修改：{'、'.join(changed)}）。请到「学工中心 → 学生信息更正」提交更正申请，"
            "审核通过后各业务域自动同步",
            http_status=410)
