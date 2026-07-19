"""同名横向越权回归测试（P0 安全修复）。

背景：此前 mobile 各业务域档案按 real_name 匹配 + .first()，同租户两个同名学生
会互相看到对方的迎新缴费 / 绿色通道 / 学业预警等敏感状态。修复：域表关联优先走带索引的
稳定外键 student_id，姓名仅在未回填 student_id 的历史行中唯一命中时才兜底；多于一条同名
一律判为无法确定 → 出空态，绝不返回他人数据。

本测试用迎新档案（/mobile/orientation/my）作为代表验证三点：
1) 他人的 FK 关联档案不会因同名被泄露；
2) 存在多条同名未关联历史行时，一律不返回（歧义即拒绝）；
3) 本人的 FK 关联档案仍能正常查到（不误伤正常访问）。
"""
from __future__ import annotations

TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _profile(db, no, name):
    from app.models import StudentProfile
    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F", grade="2023",
                       current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    return s.id


def _orientation(db, name, admission_no, *, student_id=None, payment_status="UNPAID"):
    from app.models import OrientationStudent
    db.add(OrientationStudent(tenant_id=TID, student_id=student_id, name=name,
                              admission_no=admission_no, payment_status=payment_status,
                              report_status="NOT_REPORTED", record_status="ACTIVE"))


def test_fk_linked_record_not_leaked_to_homonym(client, db_mode):
    """A 的迎新档案 FK 关联到 A；同名的 B 查询自己的迎新，绝不能看到 A 的档案。"""
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    a_id = _profile(db, "HM-A", "钱同名")
    _profile(db, "HM-B", "钱同名")  # 同名 B，无迎新档案
    _orientation(db, "钱同名", "ADM-A", student_id=a_id, payment_status="ARREARS")
    db.commit(); db.close()

    r = client.get("/api/v1/mobile/orientation/my", headers=_stu_token("钱同名", "HM-B")).json()
    assert r["code"] == 0
    # B 没有自己的迎新档案 → 空态；绝不能带出 A 的 ARREARS 欠费状态
    assert r["data"].get("hasData") is False, r["data"]
    assert r["data"].get("paymentStatus") != "ARREARS"


def test_ambiguous_unlinked_homonym_returns_empty(client, db_mode):
    """存在多条同名、均未回填 student_id 的历史行时，歧义即拒绝：不返回任何一条。"""
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    _profile(db, "HM-A2", "孙同名")
    _profile(db, "HM-B2", "孙同名")
    _orientation(db, "孙同名", "ADM-U1", student_id=None, payment_status="ARREARS")
    _orientation(db, "孙同名", "ADM-U2", student_id=None, payment_status="UNPAID")
    db.commit(); db.close()

    r = client.get("/api/v1/mobile/orientation/my", headers=_stu_token("孙同名", "HM-B2")).json()
    assert r["code"] == 0
    assert r["data"].get("hasData") is False, r["data"]


def test_own_fk_linked_record_still_visible(client, db_mode):
    """不误伤：本人 FK 关联的迎新档案仍能正常查到。"""
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    c_id = _profile(db, "HM-C", "李独名")
    _orientation(db, "李独名", "ADM-C", student_id=c_id, payment_status="PAID")
    db.commit(); db.close()

    r = client.get("/api/v1/mobile/orientation/my", headers=_stu_token("李独名", "HM-C")).json()
    assert r["code"] == 0
    assert r["data"].get("hasData") is True, r["data"]
    assert r["data"].get("paymentStatus") == "PAID"
