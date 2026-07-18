"""P3-B · 实习统计中心（指标口径 / 维度筛选 / 数据范围隔离 / 学生403 / 导出）。"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student(sno, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(tid), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """A(刘强,班级 实习2401班) ONBOARD + 打卡NORMAL + 生效协议 + 已发布成绩85；B(王芳) ONBOARD。"""
    from app.db.session import get_sessionmaker
    from app.models import (College, InternshipAgreement, InternshipCheckin, InternshipFinalScore,
                            InternshipRecord, Major, SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    ids = {}
    try:
        col = College(tenant_id=TID, college_name="信息工程学院"); db.add(col); db.flush()
        mj = Major(tenant_id=TID, college_id=col.id, major_name="软件技术"); db.add(mj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=mj.id, class_name="实习2401班"); db.add(cls); db.flush()
        for no, name, adv, key, cid in [("ST-A", "甲", "刘强", "a", cls.id), ("ST-B", "乙", "王芳", "b", None)]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, class_id=cid,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生", position_id=1,
                                 status="ONBOARD", risk_level="NONE", destination_type="ASSIGNED")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
        # A：打卡 + 协议 + 成绩
        db.add(InternshipCheckin(tenant_id=TID, internship_id=ids["rec_a"], checkin_date="2026-07-01",
                                 checkin_at=datetime.utcnow(), result="NORMAL"))
        db.add(InternshipAgreement(tenant_id=TID, internship_id=ids["rec_a"], student_id=1,
                                   status="EFFECTIVE"))
        db.add(InternshipFinalScore(tenant_id=TID, internship_id=ids["rec_a"], student_id=1,
                                    total_score=85, status="PUBLISHED", incomplete=False, is_pass=True))
        db.commit()
        return ids
    finally:
        db.close()


def _m(data, key):
    return next(m for m in data["metrics"] if m["key"] == key)


def _c(data, key):
    return next(c for c in data["counters"] if c["key"] == key)


def test_admin_metrics_correct(client, db_mode):
    _seed(db_mode)
    data = client.get(f"{INT}/stats/overview", headers=_admin(client)).json()["data"]
    assert _c(data, "totalStudents")["value"] == 2
    assert _c(data, "onboardStudents")["value"] == 2
    # 落实率口径（BUG-018）：按去向 destination_type != NONE 计，两条均为 ASSIGNED → 100
    assert _m(data, "placementRate")["rate"] == 100.0
    # 协议签署率：1 生效 / 2 → 50
    assert _m(data, "agreementSignRate")["numerator"] == 1 and _m(data, "agreementSignRate")["rate"] == 50.0
    # 打卡合规率：1 NORMAL / 1 → 100
    assert _m(data, "checkinComplyRate")["rate"] == 100.0
    # 成绩分布：良(80-89)=1
    good = next(d for d in data["scoreDistribution"] if d["bucket"].startswith("良"))
    assert good["count"] == 1
    # partial 三项已接入真实口径（就业台账 + 归档中心）
    assert _m(data, "employmentRate")["key"] == "employmentRate"
    assert _m(data, "archiveRate")["key"] == "archiveRate"
    assert data["partial"] == []


def test_scope_isolation(client, db_mode):
    _seed(db_mode)
    liu = client.get(f"{INT}/stats/overview", headers=_mentor("刘强")).json()["data"]
    wang = client.get(f"{INT}/stats/overview", headers=_mentor("王芳")).json()["data"]
    # 刘强只统计本人 1 名学生；王芳 1 名
    assert _c(liu, "totalStudents")["value"] == 1
    assert _c(wang, "totalStudents")["value"] == 1
    # 刘强的学生有协议 → 签署率 100；王芳的学生无协议 → 0
    assert _m(liu, "agreementSignRate")["rate"] == 100.0
    assert _m(wang, "agreementSignRate")["rate"] == 0.0


def test_dimension_filter(client, db_mode):
    _seed(db_mode)
    h = _admin(client)
    # 维度选项含 实习2401班
    dims = client.get(f"{INT}/stats/dimensions", headers=h).json()["data"]
    assert "实习2401班" in dims["classes"] and "信息工程学院" in dims["colleges"]
    # 按班级筛选 → 只剩 A（1 人）
    data = client.get(f"{INT}/stats/overview?className=实习2401班", headers=h).json()["data"]
    assert _c(data, "totalStudents")["value"] == 1
    assert data["dimensions"]["className"] == "实习2401班"
    # 按学院筛选
    d2 = client.get(f"{INT}/stats/overview?college=信息工程学院", headers=h).json()["data"]
    assert _c(d2, "totalStudents")["value"] == 1


def test_student_forbidden(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/stats/overview", headers=_student("ST-A")).status_code == 403
    assert client.get(f"{INT}/stats/dimensions", headers=_student("ST-A")).status_code == 403


def test_trends_respect_scope_and_return_complete_months(client, db_mode):
    _seed(db_mode)
    admin = client.get(f"{INT}/stats/trends?months=6", headers=_admin(client))
    assert admin.status_code == 200
    data = admin.json()["data"]
    assert len(data["months"]) == 6
    assert {item["key"] for item in data["series"]} == {"records", "reports", "guidance", "visits"}
    assert all(len(item["points"]) == 6 for item in data["series"])
    # 指导教师的数据范围仍必须收敛到本人所指导的实习档案。
    mentor = client.get(f"{INT}/stats/trends?months=6", headers=_mentor("刘强"))
    assert mentor.status_code == 200
    records = next(item for item in mentor.json()["data"]["series"] if item["key"] == "records")
    assert sum(point["value"] for point in records["points"]) == 1


def test_export(client, db_mode):
    _seed(db_mode)
    res = client.post(f"{INT}/stats/export", headers=_admin(client))
    assert res.status_code == 200
    d = res.json()["data"]
    assert d["filename"].endswith(".xlsx") and d["contentBase64"] and d["rowCount"] > 0


def test_placement_rate_follows_destination_not_status(client, db_mode):
    """BUG-018 回归：状态推进到 ONBOARD 但去向仍为 NONE 的记录不得计入实习落实率。

    修复前口径把「status in (READY/ONBOARD/ASSESSING/ARCHIVED)」也算作已落实，
    于是出现落实率 100% 而岗位匹配率仅 16.7% 的自相矛盾；现在与学生台账「去向」同源。
    """
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no="ST-C", real_name="丙",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        # 在岗中 + 未分配岗位 + 去向未落实（沙箱里真实存在的非法组合）
        db.add(InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name="刘强",
                                status="ONBOARD", risk_level="NONE", destination_type="NONE"))
        db.commit()
    finally:
        db.close()
    data = client.get(f"{INT}/stats/overview", headers=_admin(client)).json()["data"]
    placement = _m(data, "placementRate")
    assert placement["denominator"] == 3
    assert placement["numerator"] == 2, "去向未落实的记录不得计入落实率分子"
    assert ids  # 保持与 _seed 返回值的关联，便于失败时定位种子数据
