"""sandbox-school · 20K 真实学校主数据重建。

只负责学校主数据与身份底座：租户品牌、角色、1,280 教职工背景账号、8/32/384 组织、
20,000 学生主档、加密联系方式、20,000 学生账号、StudentAccountLink、辅导员班级范围。

业务域事实（迎新/学工/教务/实习/毕设/就业/消息待办）由后续 domain seed 基于本文件
产生的真实主键关系生成，禁止 generic marker 造关系。
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import delete, or_, select

from app.core.field_crypto import encrypt_sensitive, hash_sensitive
from app.core.security import hash_password
from app.services.sandbox_school_blueprint import (
    COLLEGE_MAJOR_BLUEPRINT,
    EXPECTED_CLASS_COUNT,
    EXPECTED_COLLEGE_COUNT,
    EXPECTED_MAJOR_COUNT,
    EXPECTED_STAFF_ACCOUNT_COUNT,
    EXPECTED_STUDENT_COUNT,
    GRADE_STUDENT_COUNTS,
    STAFF_ACCOUNT_COUNTS,
    blueprint_summary,
    iter_class_specs,
    lifecycle_stage,
    person_name,
    student_name,
    student_no,
)

SCHOOL_NAME = "跃科职业技术学院（演示）"
SCHOOL_SHORT_NAME = "跃科职院"
FIXED_LOGINS = ("admin2", "teacher2", "student2")
GENERATED_LOGIN_PREFIXES = (
    "2024S", "2025S", "2026S",
    "sbx_t", "sbx_c", "sbx_aa", "sbx_sa", "sbx_im", "sbx_gm",
)
STUDENT_BACKGROUND_PASSWORD = "Sbx@2026!"

ROLE_SPECS = (
    ("SCHOOL_ADMIN", "学校管理员"),
    ("STUDENT", "学生"),
    ("ACADEMIC_TEACHER", "任课教师"),
    ("COUNSELOR", "辅导员"),
    ("ACADEMIC_ADMIN", "教务管理员"),
    ("STUDENT_AFFAIRS_ADMIN", "学工管理员"),
    ("INTERN_MENTOR", "实习指导教师"),
    ("GD_MENTOR", "毕业设计指导教师"),
)

STAFF_PREFIX_BY_ROLE = {
    "ACADEMIC_TEACHER": "sbx_t",
    "COUNSELOR": "sbx_c",
    "ACADEMIC_ADMIN": "sbx_aa",
    "STUDENT_AFFAIRS_ADMIN": "sbx_sa",
    "INTERN_MENTOR": "sbx_im",
    "GD_MENTOR": "sbx_gm",
}


def _chunks(rows: list[dict], size: int = 1000) -> Iterable[list[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def _bulk_insert(db, model, rows: list[dict], *, chunk_size: int = 1000) -> int:
    if not rows:
        return 0
    table = model.__table__
    written = 0
    for part in _chunks(rows, chunk_size):
        db.execute(table.insert(), part)
        written += len(part)
    return written


def _generated_user_filter(User):
    return or_(*(User.login_name.like(prefix + "%") for prefix in GENERATED_LOGIN_PREFIXES))


def _remove_previous_generated_accounts(db, tenant_id: int) -> dict[str, int]:
    """t_user/t_user_role 是沙箱 reset 的保留表，因此 20K 背景账号必须单独清理。"""
    from app.models import User, UserRole

    ids = list(db.scalars(select(User.id).where(
        User.tenant_id == tenant_id,
        _generated_user_filter(User),
        User.login_name.not_in(FIXED_LOGINS),
    )))
    if not ids:
        return {"users": 0, "userRoles": 0}
    role_res = db.execute(delete(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id.in_(ids),
    ))
    user_res = db.execute(delete(User).where(
        User.tenant_id == tenant_id,
        User.id.in_(ids),
    ))
    db.commit()
    return {"users": int(user_res.rowcount or 0), "userRoles": int(role_res.rowcount or 0)}


def _ensure_tenant_and_brand(db, tenant_id: int) -> None:
    from app.models import Tenant, TenantBrandConfig
    from app.services.sandbox_service import SANDBOX_CODE

    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            tenant_code=SANDBOX_CODE,
            school_name=SCHOOL_NAME,
            short_name=SCHOOL_SHORT_NAME,
            status="ACTIVE",
        )
        db.add(tenant)
    else:
        tenant.tenant_code = SANDBOX_CODE
        tenant.school_name = SCHOOL_NAME
        tenant.short_name = SCHOOL_SHORT_NAME
        tenant.status = "ACTIVE"
        tenant.is_deleted = False

    brand = db.scalars(select(TenantBrandConfig).where(
        TenantBrandConfig.tenant_id == tenant_id,
    )).first()
    if brand is None:
        brand = TenantBrandConfig(
            tenant_id=tenant_id,
            platform_name="学生全生命周期管理平台",
            browser_title=f"{SCHOOL_SHORT_NAME} · 学生全生命周期管理平台",
            primary_color="#2563EB",
            default_theme="academy_blue",
            watermark_text="演示环境 · 数据均为虚构",
        )
        db.add(brand)
    else:
        brand.platform_name = "学生全生命周期管理平台"
        brand.browser_title = f"{SCHOOL_SHORT_NAME} · 学生全生命周期管理平台"
        brand.watermark_text = "演示环境 · 数据均为虚构"
    db.flush()


def _ensure_roles_and_fixed_accounts(db, tenant_id: int) -> dict[str, int]:
    from app.models import Role, User, UserRole

    role_by_code = {}
    for code, name in ROLE_SPECS:
        role = db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code == code,
            Role.is_deleted.is_(False),
        )).first()
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                role_code=code,
                role_name=name,
                role_type="SYSTEM",
                status="ACTIVE",
            )
            db.add(role)
            db.flush()
        else:
            role.role_name = name
            role.status = "ACTIVE"
            role.is_deleted = False
        role_by_code[code] = role

    fixed = (
        ("admin2", "胡管理", "ADMIN", "SCHOOL_ADMIN"),
        ("teacher2", "王老师", "TEACHER", "COUNSELOR"),
        ("student2", "李体验", "STUDENT", "STUDENT"),
    )
    fixed_hash = hash_password("123456")
    for login, name, user_type, role_code in fixed:
        user = db.scalars(select(User).where(
            User.tenant_id == tenant_id,
            User.login_name == login,
        )).first()
        if user is None:
            user = User(
                tenant_id=tenant_id,
                login_name=login,
                real_name=name,
                password_hash=fixed_hash,
                user_type=user_type,
                status="ACTIVE",
                must_change_password=False,
            )
            db.add(user)
            db.flush()
        else:
            user.real_name = name
            user.password_hash = fixed_hash
            user.user_type = user_type
            user.status = "ACTIVE"
            user.must_change_password = False
            user.is_deleted = False
        role = role_by_code[role_code]
        exists = db.scalars(select(UserRole).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.is_deleted.is_(False),
        )).first()
        if exists is None:
            db.add(UserRole(
                tenant_id=tenant_id,
                user_id=user.id,
                role_id=role.id,
                status="ACTIVE",
            ))
    db.commit()
    return {code: role_by_code[code].id for code, _ in ROLE_SPECS}


def _seed_staff_accounts(db, tenant_id: int, role_ids: dict[str, int]) -> dict[str, list[tuple[int, str, str]]]:
    from app.models import User, UserRole

    shared_hash = hash_password(STUDENT_BACKGROUND_PASSWORD)
    user_rows: list[dict] = []
    role_by_login: dict[str, str] = {}
    global_seq = 1
    for role_code, count in STAFF_ACCOUNT_COUNTS.items():
        prefix = STAFF_PREFIX_BY_ROLE[role_code]
        width = 4 if count >= 100 else 3
        for seq in range(1, count + 1):
            login = f"{prefix}{seq:0{width}d}"
            user_rows.append({
                "tenant_id": tenant_id,
                "login_name": login,
                "real_name": person_name(30_000 + global_seq),
                "password_hash": shared_hash,
                "user_type": "TEACHER",
                "status": "ACTIVE",
                "must_change_password": False,
            })
            role_by_login[login] = role_code
            global_seq += 1
    assert len(user_rows) == EXPECTED_STAFF_ACCOUNT_COUNT
    _bulk_insert(db, User, user_rows, chunk_size=500)
    db.flush()

    staff = list(db.execute(select(User.id, User.login_name, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_%"),
        User.is_deleted.is_(False),
    )).all())
    role_rows = [
        {
            "tenant_id": tenant_id,
            "user_id": int(user_id),
            "role_id": role_ids[role_by_login[login]],
            "status": "ACTIVE",
        }
        for user_id, login, _ in staff
        if login in role_by_login
    ]
    _bulk_insert(db, UserRole, role_rows, chunk_size=1000)
    db.commit()

    grouped: dict[str, list[tuple[int, str, str]]] = {code: [] for code in STAFF_ACCOUNT_COUNTS}
    for user_id, login, real_name in staff:
        role_code = role_by_login.get(login)
        if role_code:
            grouped[role_code].append((int(user_id), login, real_name))
    for rows in grouped.values():
        rows.sort(key=lambda x: x[1])
    return grouped


def _seed_org(db, tenant_id: int, staff: dict[str, list[tuple[int, str, str]]]) -> dict:
    from app.models import College, Major, SchoolClass

    college_rows = [
        {
            "tenant_id": tenant_id,
            "code": college_code,
            "college_name": college_name,
            "short_name": college_name.replace("学院", ""),
            "sort_order": idx,
            "status": "ACTIVE",
        }
        for idx, (college_code, college_name, _) in enumerate(COLLEGE_MAJOR_BLUEPRINT, 1)
    ]
    _bulk_insert(db, College, college_rows)
    db.flush()
    college_by_code = {
        code: (int(cid), name)
        for cid, code, name in db.execute(select(College.id, College.code, College.college_name).where(
            College.tenant_id == tenant_id,
            College.is_deleted.is_(False),
        )).all()
    }

    major_rows: list[dict] = []
    for college_code, _college_name, majors in COLLEGE_MAJOR_BLUEPRINT:
        college_id = college_by_code[college_code][0]
        for idx, major_name in enumerate(majors, 1):
            major_rows.append({
                "tenant_id": tenant_id,
                "college_id": college_id,
                "major_name": major_name,
                "code": f"{college_code}M{idx:02d}",
                "education_years": 3,
                "training_level": "HIGHER",
                "enroll_status": "ENROLLING",
                "status": "ACTIVE",
            })
    _bulk_insert(db, Major, major_rows)
    db.flush()
    major_by_code = {
        code: (int(mid), int(college_id), name)
        for mid, college_id, code, name in db.execute(select(
            Major.id, Major.college_id, Major.code, Major.major_name,
        ).where(Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).all()
    }

    counselors = staff["COUNSELOR"]
    teachers = staff["ACADEMIC_TEACHER"]
    class_rows: list[dict] = []
    for class_seq, spec in enumerate(iter_class_specs()):
        major_id = major_by_code[spec.major_code][0]
        class_rows.append({
            "tenant_id": tenant_id,
            "major_id": major_id,
            "class_name": spec.class_name,
            "grade": spec.grade,
            "counselor_id": counselors[class_seq % len(counselors)][0],
            "head_teacher_id": teachers[class_seq % len(teachers)][0],
            "status": "ACTIVE",
            "class_code": spec.class_code,
            "capacity": spec.capacity,
            "graduate_year": spec.graduate_year,
            "class_status": "NORMAL",
        })
    assert len(class_rows) == EXPECTED_CLASS_COUNT
    _bulk_insert(db, SchoolClass, class_rows)
    db.commit()

    classes = list(db.execute(select(
        SchoolClass.id, SchoolClass.class_code, SchoolClass.class_name, SchoolClass.grade,
        SchoolClass.major_id, SchoolClass.counselor_id,
    ).where(
        SchoolClass.tenant_id == tenant_id,
        SchoolClass.is_deleted.is_(False),
    ).order_by(SchoolClass.class_code)).all())
    return {
        "colleges": college_by_code,
        "majors": major_by_code,
        "classes": classes,
    }


def _student_specs(org: dict) -> list[dict]:
    classes_by_grade: dict[str, list] = {grade: [] for grade in GRADE_STUDENT_COUNTS}
    for row in org["classes"]:
        classes_by_grade[str(row.grade)].append(row)
    class_target = {spec.class_code: spec.target_students for spec in iter_class_specs()}

    specs: list[dict] = []
    global_seq = 0
    for grade in ("2024", "2025", "2026"):
        grade_seq = 1
        for row in classes_by_grade[grade]:
            target = class_target[row.class_code]
            major = next(v for v in org["majors"].values() if v[0] == int(row.major_id))
            major_id, college_id, major_name = major
            college_name = next(v[1] for v in org["colleges"].values() if v[0] == college_id)
            for _ in range(target):
                global_seq += 1
                specs.append({
                    "global_seq": global_seq,
                    "grade_seq": grade_seq,
                    "grade": grade,
                    "student_no": student_no(grade, grade_seq),
                    "name": student_name(grade, grade_seq),
                    "gender": "男" if global_seq % 2 else "女",
                    "college_id": college_id,
                    "college_name": college_name,
                    "major_id": major_id,
                    "major_name": major_name,
                    "class_id": int(row.id),
                    "class_name": row.class_name,
                    "counselor_id": int(row.counselor_id) if row.counselor_id else None,
                    "stage": lifecycle_stage(grade, grade_seq),
                })
                grade_seq += 1
        assert grade_seq - 1 == GRADE_STUDENT_COUNTS[grade]
    assert len(specs) == EXPECTED_STUDENT_COUNT
    return specs


def _synthetic_phone(global_seq: int) -> str:
    # 仅虚构数据；始终加密入库。16600000000-16600019999。
    return str(16_600_000_000 + global_seq)


def _seed_students_accounts_contacts(db, tenant_id: int, role_ids: dict[str, int], org: dict) -> dict:
    from app.models import StudentAccountLink, StudentContact, StudentProfile, User, UserRole

    specs = _student_specs(org)
    profile_rows = []
    for item in specs:
        profile_rows.append({
            "tenant_id": tenant_id,
            "student_no": item["student_no"],
            "real_name": item["name"],
            "gender": item["gender"],
            "college_id": item["college_id"],
            "major_id": item["major_id"],
            "class_id": item["class_id"],
            "grade": item["grade"],
            "current_stage": item["stage"],
            "student_status": "NORMAL",
            "data_quality_status": "VERIFIED",
            "enroll_date": None if item["grade"] == "2026" else datetime(int(item["grade"]), 9, 1),
            "status": "ACTIVE",
        })
    _bulk_insert(db, StudentProfile, profile_rows, chunk_size=1000)
    db.flush()

    profiles = list(db.execute(select(
        StudentProfile.id, StudentProfile.student_no, StudentProfile.real_name,
    ).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )).all())
    profile_by_no = {row.student_no: (int(row.id), row.real_name) for row in profiles}
    assert len(profile_by_no) == EXPECTED_STUDENT_COUNT

    contact_rows: list[dict] = []
    for item in specs:
        phone = _synthetic_phone(item["global_seq"])
        sid = profile_by_no[item["student_no"]][0]
        contact_rows.append({
            "tenant_id": tenant_id,
            "student_id": sid,
            "contact_type": "PHONE",
            "contact_value_encrypted": encrypt_sensitive(phone, "phone"),
            "contact_value_hash": hash_sensitive(phone, "phone"),
            "verified_status": "VERIFIED",
            "is_primary": True,
        })
    _bulk_insert(db, StudentContact, contact_rows, chunk_size=500)

    shared_hash = hash_password(STUDENT_BACKGROUND_PASSWORD)
    account_rows: list[dict] = []
    for item in specs:
        if item["student_no"] == "2026S0001":
            continue  # 固定 student2 作为这名学生的可见登录账号。
        account_rows.append({
            "tenant_id": tenant_id,
            "login_name": item["student_no"],
            "real_name": item["name"],
            "password_hash": shared_hash,
            "user_type": "STUDENT",
            "status": "ACTIVE",
            "must_change_password": False,
        })
    _bulk_insert(db, User, account_rows, chunk_size=500)
    db.flush()

    student2 = db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.login_name == "student2",
        User.is_deleted.is_(False),
    )).one()
    users = list(db.execute(select(User.id, User.login_name).where(
        User.tenant_id == tenant_id,
        or_(User.login_name.like("2024S%"), User.login_name.like("2025S%"), User.login_name.like("2026S%")),
        User.is_deleted.is_(False),
    )).all())
    user_by_login = {login: int(uid) for uid, login in users}
    user_by_login["2026S0001"] = int(student2.id)
    assert len(user_by_login) == EXPECTED_STUDENT_COUNT

    link_rows: list[dict] = []
    role_rows: list[dict] = []
    for item in specs:
        sid = profile_by_no[item["student_no"]][0]
        uid = user_by_login[item["student_no"]]
        link_rows.append({
            "tenant_id": tenant_id,
            "student_id": sid,
            "user_id": uid,
            "link_status": "ACTIVE",
            "bound_login_name": "student2" if item["student_no"] == "2026S0001" else item["student_no"],
            "bound_student_no": item["student_no"],
            "source": "IDENTITY_IMPORT",
            "bound_at": datetime(2026, 8, 1, 9, 0),
            "remark": "演示沙箱真实学校数据标准批量身份绑定",
        })
        if item["student_no"] != "2026S0001":
            role_rows.append({
                "tenant_id": tenant_id,
                "user_id": uid,
                "role_id": role_ids["STUDENT"],
                "status": "ACTIVE",
            })
    _bulk_insert(db, StudentAccountLink, link_rows, chunk_size=1000)
    _bulk_insert(db, UserRole, role_rows, chunk_size=1000)
    db.commit()
    return {
        "specs": specs,
        "profileByNo": profile_by_no,
        "userByStudentNo": user_by_login,
    }


def _seed_teacher_scopes(db, tenant_id: int, staff: dict[str, list[tuple[int, str, str]]], org: dict) -> int:
    from app.models import TeacherStudentScope, User

    counselor_by_id = {uid: (login, name) for uid, login, name in staff["COUNSELOR"]}
    rows: list[dict] = []
    for cls in org["classes"]:
        if not cls.counselor_id:
            continue
        login, name = counselor_by_id[int(cls.counselor_id)]
        rows.append({
            "tenant_id": tenant_id,
            "teacher_key": login,
            "teacher_name": name,
            "role_code": "COUNSELOR",
            "scope_type": "CLASS",
            "ref_value": cls.class_name,
            "status": "ACTIVE",
        })
    # teacher2 保持可直接体验辅导员视角，绑定前两个 2026 级班。
    first_2026 = [x for x in org["classes"] if str(x.grade) == "2026"][:2]
    for cls in first_2026:
        rows.append({
            "tenant_id": tenant_id,
            "teacher_key": "teacher2",
            "teacher_name": "王老师",
            "role_code": "COUNSELOR",
            "scope_type": "CLASS",
            "ref_value": cls.class_name,
            "status": "ACTIVE",
        })
    _bulk_insert(db, TeacherStudentScope, rows, chunk_size=1000)
    db.commit()
    return len(rows)


def validate_school_master(db, tenant_id: int) -> dict:
    from sqlalchemy import func
    from app.models import College, Major, SchoolClass, StudentAccountLink, StudentProfile, User

    def count(model, *extra):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *extra,
        )) or 0)

    students = count(StudentProfile, StudentProfile.is_deleted.is_(False))
    colleges = count(College, College.is_deleted.is_(False))
    majors = count(Major, Major.is_deleted.is_(False))
    classes = count(SchoolClass, SchoolClass.is_deleted.is_(False))
    links = count(StudentAccountLink, StudentAccountLink.link_status == "ACTIVE", StudentAccountLink.is_deleted.is_(False))
    background_staff = count(User, User.login_name.like("sbx_%"), User.is_deleted.is_(False))
    student_accounts = count(
        User,
        or_(User.login_name.like("2024S%"), User.login_name.like("2025S%"), User.login_name.like("2026S%")),
        User.is_deleted.is_(False),
    ) + count(User, User.login_name == "student2", User.is_deleted.is_(False))

    report = {
        "students": students,
        "colleges": colleges,
        "majors": majors,
        "classes": classes,
        "activeStudentLinks": links,
        "studentAccounts": student_accounts,
        "backgroundStaffAccounts": background_staff,
    }
    expected = {
        "students": EXPECTED_STUDENT_COUNT,
        "colleges": EXPECTED_COLLEGE_COUNT,
        "majors": EXPECTED_MAJOR_COUNT,
        "classes": EXPECTED_CLASS_COUNT,
        "activeStudentLinks": EXPECTED_STUDENT_COUNT,
        "studentAccounts": EXPECTED_STUDENT_COUNT,
        "backgroundStaffAccounts": EXPECTED_STAFF_ACCOUNT_COUNT,
    }
    mismatches = {k: {"expected": expected[k], "actual": report[k]} for k in expected if report[k] != expected[k]}
    if mismatches:
        raise RuntimeError(f"20K 沙箱主数据验收失败: {mismatches}")
    report["passed"] = True
    return report


def rebuild_school_master_20k(db) -> dict:
    """破坏性重建 sandbox-school 主数据；调用方必须已经明确选择该固定沙箱租户。"""
    from app.services.sandbox_service import SANDBOX_TID, _assert_target_is_sandbox, wipe_sandbox

    _assert_target_is_sandbox(db)
    # 先清租户业务表；t_user/t_role/t_user_role 是历史 reset 保留表，再单独清理本生成器背景账号。
    removed_business = wipe_sandbox(db)
    removed_accounts = _remove_previous_generated_accounts(db, SANDBOX_TID)
    _ensure_tenant_and_brand(db, SANDBOX_TID)
    role_ids = _ensure_roles_and_fixed_accounts(db, SANDBOX_TID)
    staff = _seed_staff_accounts(db, SANDBOX_TID, role_ids)
    org = _seed_org(db, SANDBOX_TID, staff)
    students = _seed_students_accounts_contacts(db, SANDBOX_TID, role_ids, org)
    scope_rows = _seed_teacher_scopes(db, SANDBOX_TID, staff, org)
    validation = validate_school_master(db, SANDBOX_TID)
    return {
        "profile": blueprint_summary(),
        "removedBusiness": removed_business,
        "removedGeneratedAccounts": removed_accounts,
        "students": len(students["specs"]),
        "teacherScopeRows": scope_rows,
        "validation": validation,
    }
