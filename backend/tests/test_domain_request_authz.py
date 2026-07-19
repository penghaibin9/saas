"""生产级审计 P1-1/P1-2 整改验收：迎新 / 就业 / 学业过程域的 router 级权限码门禁。

此前三域仅身份门禁（require_staff 只拦学生）：宿管、任课老师、实习导师等任意教职工
都能读全量新生隐私、标注就业去向、改成绩预警。本文件锁定整改后的能力边界：
- 读 → <domain>.view；导出 → .export；写 → .manage（fail-closed）
- 学工处/学院/校管理员经 ROLE_PERMISSIONS 通配命中；宿管/导师等一律 403
数据范围（本班/本院）由 service 层另行收敛，这里只验角色级能力门禁。
"""
from __future__ import annotations

TID = 1000000000000000001


def _tok(role, user_type="TEACHER", client_type="PC"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{role}", "realName": role, "userType": user_type,
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": client_type})}


# ── 数字迎新（studentAffairs.orientation.*）──

def test_orientation_denies_unrelated_staff(client, db_mode):
    """宿管/实习导师/毕设导师：读写迎新一律 403（此前全部放行——本次整改主目标）。"""
    for role in ("DORM_MANAGER", "INTERN_MENTOR", "GD_MENTOR"):
        h = _tok(role)
        assert client.get("/api/v1/orientation/students", headers=h).status_code == 403, role
        assert client.post("/api/v1/orientation/students", headers=h,
                           json={"name": "x"}).status_code == 403, role


def test_orientation_allows_student_affairs_roles(client, db_mode):
    """学工处管理员/学院管理员/校管理员：迎新读操作放行（studentAffairs.* 通配）。"""
    for role in ("STUDENT_AFFAIRS_ADMIN", "COLLEGE_ADMIN", "SCHOOL_ADMIN"):
        h = _tok(role)
        assert client.get("/api/v1/orientation/dashboard", headers=h).status_code == 200, role


def test_orientation_leader_read_only(client, db_mode):
    """校领导：只读（*.view 通配），写 403。"""
    h = _tok("LEADER")
    assert client.get("/api/v1/orientation/dashboard", headers=h).status_code == 200
    assert client.post("/api/v1/orientation/students", headers=h,
                       json={"name": "x"}).status_code == 403


def test_orientation_blocks_student(client, db_mode):
    """学生令牌：403（require_staff 维持不变）。"""
    h = _tok("STUDENT", user_type="STUDENT")
    assert client.get("/api/v1/orientation/students", headers=h).status_code == 403


# ── 就业服务（employment.*）──

def test_employment_denies_unrelated_staff(client, db_mode):
    """宿管/任课老师：就业域读写一律 403（此前任意教职工可标注就业去向）。"""
    for role in ("DORM_MANAGER", "ACADEMIC_TEACHER"):
        h = _tok(role)
        assert client.get("/api/v1/employment/students", headers=h).status_code == 403, role
        assert client.post("/api/v1/employment/students", headers=h,
                           json={"name": "x"}).status_code == 403, role


def test_employment_allows_employment_teacher(client, db_mode):
    """就业老师（employment.* 授予）与校管理员：读放行。"""
    for role in ("EMPLOYMENT_TEACHER", "SCHOOL_ADMIN"):
        h = _tok(role)
        assert client.get("/api/v1/employment/dashboard", headers=h).status_code == 200, role


# ── 学业过程（academicAffairs.process.*）──

def test_academic_process_denies_unrelated_staff(client, db_mode):
    """宿管/就业老师：学业过程域读写一律 403（此前任意教职工可改成绩/预警）。"""
    for role in ("DORM_MANAGER", "EMPLOYMENT_TEACHER"):
        h = _tok(role)
        assert client.get("/api/v1/academic/students", headers=h).status_code == 403, role
        assert client.post("/api/v1/academic/grades", headers=h,
                           json={"studentId": "x"}).status_code == 403, role


def test_academic_process_allows_academic_roles(client, db_mode):
    """教务老师/教务处管理员/校管理员：读放行（academicAffairs.* 通配）。"""
    for role in ("ACADEMIC_TEACHER", "ACADEMIC_ADMIN", "SCHOOL_ADMIN"):
        h = _tok(role)
        assert client.get("/api/v1/academic/dashboard", headers=h).status_code == 200, role
