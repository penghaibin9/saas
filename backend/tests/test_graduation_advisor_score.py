"""毕业设计中心 · 导师评分：导师只给本人指导、定稿已通过的学生打导师分。"""
from __future__ import annotations

from datetime import datetime

from conftest import make_org_class

GD_GRADE = "/api/v1/graduation/gd-grades"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _mentor_headers(no, name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{no}-M", "realName": name, "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "GD_MENTOR", "clientType": "PC", "loginName": f"{no}-M",
    })}


def _student(graduation_client, h, no, name, advisor, final_status="APPROVED"):
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationMentor, GraduationStudent

    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    try:
        mentor = GraduationMentor(
            tenant_id=1000000000000000001, teacher_no=f"{no}-M",
            teacher_name=advisor, qualification_status="QUALIFIED",
        )
        db.add(mentor)
        db.flush()
        stu = db.get(GraduationStudent, int(gid))
        stu.mentor_id = mentor.id
        stu.advisor_name = advisor
        if final_status:
            db.add(GraduationFinal(
                tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
                version="v1", submit_at=datetime.utcnow(), status=final_status,
                plagiarism_rate="10.0%", plagiarism_status="已检测", attachments_json=["f"],
            ))
        db.commit()
        return gid
    finally:
        db.close()


def test_mentor_scores_own_student_after_final_approved(graduation_client, auth_headers, db_mode):
    gid = _student(graduation_client, auth_headers, "AS001", "导师分测试生", "导师甲")
    mh = _mentor_headers("AS001", "导师甲")
    ok = graduation_client.post(f"{GD_GRADE}/{gid}/advisor-score", headers=mh, json={"score": 88, "comment": "过程认真"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["advisorScore"] == 88
    assert ok.json()["data"]["status"] == "DRAFT"  # 只写导师分，不核算综合分
    assert ok.json()["data"]["totalScore"] is None

    again = graduation_client.post(f"{GD_GRADE}/{gid}/advisor-score", headers=mh, json={"score": 90})
    assert again.json()["data"]["advisorScore"] == 90


def test_other_teacher_cannot_score(graduation_client, auth_headers, db_mode):
    gid = _student(graduation_client, auth_headers, "AS002", "他人学生", "导师乙")
    other = _mentor_headers("AS002X", "导师丙")
    res = graduation_client.post(f"{GD_GRADE}/{gid}/advisor-score", headers=other, json={"score": 80})
    body = res.json()
    # 必须是“无权限/找不到”，不能因为别的原因（如定稿未通过 409）而恰好失败。
    assert res.status_code in (403, 404) or str(body.get("code", "")).startswith(("403", "404")), res.text
    assert res.status_code != 409 and not str(body.get("code", "")).startswith("409"), res.text


def test_final_not_approved_blocks_score(graduation_client, auth_headers, db_mode):
    gid = _student(graduation_client, auth_headers, "AS003", "未过定稿生", "导师丁", final_status="PENDING_REVIEW")
    res = graduation_client.post(
        f"{GD_GRADE}/{gid}/advisor-score", headers=_mentor_headers("AS003", "导师丁"), json={"score": 80})
    assert res.status_code == 409
    assert "定稿" in res.text


def test_score_range_validated(graduation_client, auth_headers, db_mode):
    gid = _student(graduation_client, auth_headers, "AS004", "分数范围生", "导师戊")
    res = graduation_client.post(
        f"{GD_GRADE}/{gid}/advisor-score", headers=_mentor_headers("AS004", "导师戊"), json={"score": 101})
    assert res.status_code in (400, 422)
