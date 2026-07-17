"""就业中心 · 移动端就业老师转交学生（保守设计：仅可转交本人负责的学生）。

employment_service 全模块无调用者范围收敛、employment_teacher 为自由文本字段，移动端
transfer 采用最小安全实现——仅当目标学生 employment_teacher 精确等于调用者 realName 时放行。
mock 账号 employment01 的 realName=刘芳。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
MAIN_TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """两个就业学生：mine 归属"刘芳"(employment01 本人)，other 归属"别的老师"。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent
    db = get_sessionmaker()()
    try:
        mine = EmpStudent(tenant_id=MAIN_TID, name="我的就业生", student_no="ET001",
                          class_name="软件2101", destination_type="NONE", verify_status="PENDING",
                          employment_teacher="刘芳")
        other = EmpStudent(tenant_id=MAIN_TID, name="他人就业生", student_no="ET002",
                           class_name="软件2102", destination_type="NONE", verify_status="PENDING",
                           employment_teacher="王老师")
        db.add(mine); db.add(other); db.flush()
        ids = {"mine": mine.id, "other": other.id}
        db.commit()
        return ids
    finally:
        db.close()


def test_my_students_only_returns_mine(client, db_mode):
    """「我负责的学生」只返回 employment_teacher==本人 realName 的学生。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "employment01")
    r = client.get(f"{MOB}/teacher/employment/my-students", headers=hdr).json()
    assert r["code"] == 0
    names = {s["name"] for s in r["data"]["list"]}
    assert "我的就业生" in names and "他人就业生" not in names


def test_transfer_own_student_success(client, db_mode):
    """转交本人负责的学生成功，学生归属变更为新老师。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "employment01")
    r = client.post(f"{MOB}/teacher/employment/students/{ids['mine']}/transfer", headers=hdr,
                    json={"newTeacher": "赵老师"})
    assert r.status_code == 200 and r.json()["code"] == 0

    # get_student_detail 返回 {"student": {...}, "materials": ...}，归属字段在 student 子对象里
    detail = client.get(f"/api/v1/employment/students/{ids['mine']}", headers=hdr).json()["data"]
    assert detail["student"]["employmentTeacher"] == "赵老师"
    # 转交后不再出现在「我负责的学生」里
    mine = client.get(f"{MOB}/teacher/employment/my-students", headers=hdr).json()["data"]["list"]
    assert not any(s["id"] == str(ids["mine"]) for s in mine)


def test_transfer_others_student_403(client, db_mode):
    """转交非本人负责的学生 → 403（保守设计核心断言）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "employment01")
    r = client.post(f"{MOB}/teacher/employment/students/{ids['other']}/transfer", headers=hdr,
                    json={"newTeacher": "赵老师"})
    assert r.status_code == 403


def test_transfer_empty_new_teacher_400(client, db_mode):
    """接收老师姓名为空 → 400。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "employment01")
    r = client.post(f"{MOB}/teacher/employment/students/{ids['mine']}/transfer", headers=hdr,
                    json={"newTeacher": "  "})
    assert r.status_code == 400
