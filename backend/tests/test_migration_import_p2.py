"""老系统数据迁移 P2·15 域：学工链路(房源/分配/请假/联系人)、学工历史(资助/处分/谈话/风险/班干部)、
教务链路(课程/方案/任务/课表冲突)、毕业结论交叉校验、总览 21 域。"""
from __future__ import annotations

MAIN_TID = 1000000000000000001


def _seed_students(client, auth_headers, nos, gender=None):
    """直接经统一主档服务造数据（旧 /import/students/* 已随入口收敛删除）。"""
    from app.core.student_master_contract import StudentCreateCommand
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master
    db = get_sessionmaker()()
    try:
        for i, no in enumerate(nos):
            master.create_student_in_session(
                db, tenant_id=MAIN_TID,
                cmd=StudentCreateCommand(student_no=no, real_name=f"生{i}", gender=gender))
        db.commit()
    finally:
        db.close()


def _seed_org(class_name="软件2301班", major_name="软件技术"):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=MAIN_TID, college_name="信息学院")
        db.add(col); db.flush()
        major = Major(tenant_id=MAIN_TID, college_id=col.id, major_name=major_name)
        db.add(major); db.flush()
        cls = SchoolClass(tenant_id=MAIN_TID, major_id=major.id, class_name=class_name, grade="2023")
        db.add(cls); db.flush()
        db.commit()
        return {"collegeId": col.id, "majorId": major.id, "classId": cls.id}
    finally:
        db.close()


def _run(client, auth_headers, domain, rows, expect_pass=True):
    dr = client.post(f"/api/v1/system/migration/domains/{domain}/validate",
                     headers=auth_headers, json={"rows": rows}).json()
    assert dr["code"] == 0, dr
    if expect_pass:
        assert dr["data"]["status"] == "DRY_RUN_PASSED", dr["data"]["errors"]
        cf = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                         json={"batchNo": dr["data"]["batchNo"]}).json()
        assert cf["code"] == 0, cf
        return cf["data"]
    return dr["data"]


def test_overview_lists_all_21_domains(client, auth_headers, db_mode):
    ov = client.get("/api/v1/system/migration/overview", headers=auth_headers).json()
    domains = ov["data"]["domains"]
    assert len(domains) == 21
    assert [d["order"] for d in domains] == list(range(1, 22))
    by = {d["domain"]: d for d in domains}
    assert by["affairs-dorm-assign"]["dependsOn"] == ["student-profile", "affairs-dorm-building"]
    assert by["aa-schedule"]["dependsMet"] is False  # 无作息/教学任务


def test_dorm_chain_and_leave_and_contact(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["P2D001", "P2D002"], gender="女")
    # A1 房源：1 房 3 床
    r1 = _run(client, auth_headers, "affairs-dorm-building",
              [{"buildingCode": "B01", "buildingName": "梅苑1栋", "genderLimit": "女",
                "floorNo": "3", "roomNo": "302", "capacity": "3"}])
    assert r1["created"] == 1
    # A2 分配：成功 1 行；床位重复+学生重复报错
    _run(client, auth_headers, "affairs-dorm-assign",
         [{"studentNo": "P2D001", "buildingCode": "B01", "roomNo": "302", "bedNo": "1"}])
    bad = _run(client, auth_headers, "affairs-dorm-assign",
               [{"studentNo": "P2D002", "buildingCode": "B01", "roomNo": "302", "bedNo": "1"},
                {"studentNo": "P2D001", "buildingCode": "B01", "roomNo": "302", "bedNo": "2"}],
               expect_pass=False)
    codes = {e["errorCode"] for e in bad["errors"]}
    assert {"BED_OCCUPIED", "DUP_IN_DB"} <= codes
    # 房源覆盖：容量缩到 0 个占用以下报 BED_OCCUPIED_SHRINK
    shrink = _run(client, auth_headers, "affairs-dorm-building",
                  [{"buildingCode": "B01", "buildingName": "梅苑1栋", "genderLimit": "女",
                    "floorNo": "3", "roomNo": "302", "capacity": "0"}], expect_pass=False)
    assert any(e["errorCode"] in ("RANGE_INVALID", "BED_OCCUPIED_SHRINK") for e in shrink["errors"])
    # 回写 t_cs_dorm_record
    from app.db.session import get_sessionmaker
    from app.models import CsDormRecord, DormBed
    from sqlalchemy import select
    db = get_sessionmaker()()
    try:
        bed = db.scalars(select(DormBed).where(DormBed.bed_no == "1", DormBed.status == "OCCUPIED")).first()
        assert bed is not None and bed.cs_dorm_record_id
        assert db.get(CsDormRecord, bed.cs_dorm_record_id).bed == "1"
    finally:
        db.close()
    # A3 请假历史：CLOSED 必带返校时间；终态入库
    bad_leave = _run(client, auth_headers, "affairs-leave-history",
                     [{"studentNo": "P2D001", "leaveType": "病假", "startTime": "2025-03-02 08:00",
                       "endTime": "2025-03-05 08:00", "reason": "流感就医", "finalStatus": "已销假"}],
                     expect_pass=False)
    assert bad_leave["errors"][0]["errorCode"] == "REQUIRED_MISSING"
    _run(client, auth_headers, "affairs-leave-history",
         [{"studentNo": "P2D001", "leaveType": "病假", "startTime": "2025-03-02 08:00",
           "endTime": "2025-03-05 08:00", "reason": "流感就医", "finalStatus": "已销假",
           "actualReturnAt": "2025-03-05 09:00"}])
    # A8 家庭联系人：预览脱敏 + OVERWRITE
    dr = client.post("/api/v1/system/migration/domains/affairs-family-contact/validate",
                     headers=auth_headers,
                     json={"rows": [{"studentNo": "P2D001", "contactType": "监护人",
                                     "contactName": "张建国", "phone": "13800001234"}]}).json()
    assert dr["data"]["rows"][0]["phone"] == "138****1234"  # 预览行脱敏
    assert client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                       json={"batchNo": dr["data"]["batchNo"]}).json()["code"] == 0
    again = _run(client, auth_headers, "affairs-family-contact",
                 [{"studentNo": "P2D001", "contactType": "监护人",
                   "contactName": "张建国", "phone": "13900005678"}])
    assert again.get("updated") == 1  # OVERWRITE 以最新导入为准


def test_affairs_history_domains(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["P2H001"])
    org = _seed_org()
    # A10 班干部（SKIP 幂等）
    row = {"className": "软件2301班", "studentNo": "P2H001", "position": "班长",
           "termCode": "2024-2025-1", "appointedAt": "2024-09-10"}
    _run(client, auth_headers, "affairs-class-cadre", [row])
    redo = client.post("/api/v1/system/migration/domains/affairs-class-cadre/validate",
                       headers=auth_headers, json={"rows": [row]}).json()["data"]
    assert redo["skippedRows"] == 1 and redo["errorRows"] == 0
    # A4 困难认定 + 重复 ERROR
    _run(client, auth_headers, "affairs-aid-history",
         [{"studentNo": "P2H001", "yearCode": "2024-2025", "finalLevel": "困难",
           "identifiedAt": "2024-10-15"}])
    dup = _run(client, auth_headers, "affairs-aid-history",
               [{"studentNo": "P2H001", "yearCode": "2024-2025", "finalLevel": "一般困难",
                 "identifiedAt": "2024-10-16"}], expect_pass=False)
    assert dup["errors"][0]["errorCode"] == "DUP_IN_DB"
    # A5 奖助（项目自动预建 + StageEvent）
    _run(client, auth_headers, "affairs-funding-history",
         [{"studentNo": "P2H001", "projectName": "国家励志奖学金", "projectType": "奖学金",
           "yearCode": "2024-2025", "amount": "5000", "resultAt": "2024-12-01"}])
    # A6 处分（投影链路）
    _run(client, auth_headers, "affairs-discipline-history",
         [{"studentNo": "P2H001", "discType": "警告", "docNo": "校学字〔2024〕12号",
           "decideDate": "2024-05-20", "reason": "考试作弊", "removed": "否"}])
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline, DisciplineCase, FundingProject, StudentStageEvent
    from sqlalchemy import select
    db = get_sessionmaker()()
    try:
        case = db.scalars(select(DisciplineCase)).first()
        proj = db.get(CsDiscipline, case.cs_discipline_id)
        assert proj.source_case_id == case.id and proj.doc_no == case.doc_no
        assert db.scalars(select(FundingProject).where(
            FundingProject.project_name == "国家励志奖学金")).first() is not None
        assert db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.to_stage == "FUNDING_GRANTED")).first() is not None
    finally:
        db.close()
    # A7 谈话：心理类预览打码 + SKIP 幂等
    talk = {"studentNo": "P2H001", "teacherKey": "T0012", "topicType": "心理",
            "talkAt": "2024-11-05 15:00", "content": "情绪低落，持续关注并转介心理中心"}
    dr = client.post("/api/v1/system/migration/domains/affairs-talk-history/validate",
                     headers=auth_headers, json={"rows": [talk]}).json()["data"]
    assert "仅授权角色可见" in dr["rows"][0]["content"]
    assert client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                       json={"batchNo": dr["batchNo"]}).json()["code"] == 0
    redo = client.post("/api/v1/system/migration/domains/affairs-talk-history/validate",
                       headers=auth_headers, json={"rows": [talk]}).json()["data"]
    assert redo["skippedRows"] == 1
    # A9 风险名单（SKIP 幂等）
    risk = {"studentNo": "P2H001", "riskLevel": "高", "description": "多门课程不及格且旷课频繁",
            "riskStatus": "在管"}
    _run(client, auth_headers, "affairs-risk-manual", [risk])
    redo = client.post("/api/v1/system/migration/domains/affairs-risk-manual/validate",
                       headers=auth_headers, json={"rows": [risk]}).json()["data"]
    assert redo["skippedRows"] == 1


def test_academic_chain_course_program_task_schedule(client, auth_headers, db_mode):
    _seed_org()
    # 依赖：学期 + 作息
    _run(client, auth_headers, "aa-term",
         [{"yearCode": "2024-2025", "termNo": "1", "startDate": "2024-09-02",
           "endDate": "2025-01-17", "teachingWeeks": "18"}])
    _run(client, auth_headers, "aa-time-slot",
         [{"slotNo": "1", "startTime": "08:00", "endTime": "08:45"},
          {"slotNo": "2", "startTime": "08:55", "endTime": "09:40"}])
    # B6 课程库 + OVERWRITE(DRAFT)
    _run(client, auth_headers, "aa-course",
         [{"courseCode": "C0101", "courseName": "数据库原理", "category": "专业核心",
           "nature": "必修", "credit": "3.5", "hoursTheory": "48", "hoursPractice": "16"}])
    redo = _run(client, auth_headers, "aa-course",
                [{"courseCode": "C0101", "courseName": "数据库原理(修订)", "category": "专业核心",
                  "nature": "必修", "credit": "4", "hoursTheory": "56", "hoursPractice": "16"}])
    assert redo["updated"] == 1
    # B7 培养方案（分组行）
    r = _run(client, auth_headers, "aa-program",
             [{"programName": "软件技术2023级方案", "majorName": "软件技术", "gradeYear": "2023",
               "totalCredits": "152", "courseCode": "C0101", "openTermNo": "3", "module": "专业"}])
    assert r["created"] == 1 and r["courseRows"] == 1
    dup = _run(client, auth_headers, "aa-program",
               [{"programName": "软件技术2023级方案", "majorName": "软件技术", "gradeYear": "2023",
                 "totalCredits": "152", "courseCode": "C0101", "openTermNo": "3", "module": "专业"}],
               expect_pass=False)
    assert dup["errors"][0]["errorCode"] == "DUP_IN_DB"
    # B8 教学任务
    _run(client, auth_headers, "aa-teaching-task",
         [{"yearCode": "2024-2025", "termNo": "1", "courseCode": "C0101",
           "className": "软件2301班", "teacherKey": "T0012", "weeklyHours": "4"}])
    # B9 课表：合法行 + 班级冲突行
    r = _run(client, auth_headers, "aa-schedule",
             [{"yearCode": "2024-2025", "termNo": "1", "courseCode": "C0101",
               "className": "软件2301班", "weekday": "3", "slotNo": "2",
               "startWeek": "1", "endWeek": "16", "classroom": "实训楼301"}])
    assert r["created"] == 1
    conflict = _run(client, auth_headers, "aa-schedule",
                    [{"yearCode": "2024-2025", "termNo": "1", "courseCode": "C0101",
                      "className": "软件2301班", "weekday": "3", "slotNo": "2",
                      "startWeek": "8", "endWeek": "10"}], expect_pass=False)
    assert conflict["errors"][0]["errorCode"] == "CONFLICT_CLASS"


def test_graduation_history_cross_check(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["P2G001", "P2G002"])
    # 先把 P2G002 迁为退学
    _run(client, auth_headers, "aa-student-status",
         [{"studentNo": "P2G002", "studentStatus": "退学", "effectiveDate": "2022-09-01",
           "reason": "个人原因退学"}])
    bad = _run(client, auth_headers, "aa-graduation-history",
               [{"studentNo": "P2G002", "graduateYear": "2023", "conclusion": "毕业",
                 "concludedAt": "2023-06-30"}], expect_pass=False)
    assert bad["errors"][0]["errorCode"] == "CROSS_CHECK_FAILED"
    _run(client, auth_headers, "aa-graduation-history",
         [{"studentNo": "P2G001", "graduateYear": "2023", "conclusion": "毕业",
           "concludedAt": "2023-06-30"}])
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult
    from sqlalchemy import select
    db = get_sessionmaker()()
    try:
        res = db.scalars(select(AaGraduationAuditResult)).first()
        assert res.conclusion == "GRADUATED" and res.status == "ARCHIVED"
        assert "2023届" in db.get(AaGraduationAuditBatch, res.batch_id).batch_name
    finally:
        db.close()
