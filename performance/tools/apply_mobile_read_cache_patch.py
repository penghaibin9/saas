#!/usr/bin/env python3
"""One-time exact patch for E capacity mobile-read caching and class-count N+1 removal."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE_API = ROOT / "backend/app/api/v1/mobile.py"
TEACHER = ROOT / "backend/app/services/mobile_teacher_service.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


mobile = MOBILE_API.read_text(encoding="utf-8")
mobile = replace_once(
    mobile,
    "from app.services import mobile_teacher_service as tea\n",
    "from app.services import mobile_teacher_service as tea\n"
    "from app.services import mobile_read_cache as read_cache\n",
    "mobile cache import",
)

replacements = {
    "    return success(stu.my_todos(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"student-todos\", lambda: stu.my_todos(user)))\n",
    "    return success(stu.my_messages(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"student-messages\", lambda: stu.my_messages(user)))\n",
    "    return success(stu.my_profile(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"student-profile\", lambda: stu.my_profile(user)))\n",
    "    return success(tea.overview(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"teacher-overview\", lambda: tea.overview(user)))\n",
    "    return success(tea.todos(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"teacher-todos\", lambda: tea.todos(user)))\n",
    "    return success(tea.risk_students(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"teacher-risk-students\", lambda: tea.risk_students(user)))\n",
    "    return success(tea.my_classes(user))\n":
        "    return success(read_cache.cached_mobile_read(user, \"teacher-my-classes\", lambda: tea.my_classes(user)))\n",
}
for old, new in replacements.items():
    mobile = replace_once(mobile, old, new, old.strip())
MOBILE_API.write_text(mobile, encoding="utf-8")

teacher = TEACHER.read_text(encoding="utf-8")
old_block = '''        rows = db.scalars(select(SchoolClass).where(*conds).order_by(SchoolClass.id.desc())).all()
        out = []
        for c in rows:
            cnt = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == tid, StudentProfile.class_id == c.id,
                StudentProfile.is_deleted.is_(False))) or 0
            out.append({"classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                       "studentCount": cnt, "status": c.status})
        return {"hasData": bool(out), "items": out}
'''
new_block = '''        rows = db.scalars(select(SchoolClass).where(*conds).order_by(SchoolClass.id.desc())).all()
        class_ids = [c.id for c in rows]
        counts = {}
        if class_ids:
            counts = dict(db.execute(
                select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
                    StudentProfile.tenant_id == tid,
                    StudentProfile.class_id.in_(class_ids),
                    StudentProfile.is_deleted.is_(False),
                ).group_by(StudentProfile.class_id)
            ).all())
        out = [
            {"classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
             "studentCount": int(counts.get(c.id, 0)), "status": c.status}
            for c in rows
        ]
        return {"hasData": bool(out), "items": out}
'''
teacher = replace_once(teacher, old_block, new_block, "teacher my_classes grouped count")
TEACHER.write_text(teacher, encoding="utf-8")
print("mobile read cache patch applied")
