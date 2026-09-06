#!/usr/bin/env python3
"""只读审计全校学生、宿舍、迎新 Authority 一致性。

用法：python scripts/audit_school_authority_consistency.py --tenant-id 1000000000000000001
脚本从不 flush/commit，不修数据；发现问题返回退出码 2，供上线 Gate 阻断。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.context import set_tenant  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402


def audit(tenant_id: int) -> dict:
    from app.models import (
        AcademicStudent, CsDormRecord, CsServiceStudent, DormBed, DormBuilding,
        DormRoom, DormStay, EmpStudent, GraduationStudent, InternshipRecord,
        OrientationBatch, OrientationFlowStep, OrientationQualificationDecision,
        OrientationFlowVersion, OrientationStudent, OrientationStudentStep,
        StudentAccountLink, StudentProfile,
        User,
    )

    set_tenant(tenant_id)
    issues: list[dict] = []

    def add(domain: str, code: str, entity, detail: str):
        issues.append({
            "domain": domain, "code": code,
            "entityId": str(entity or ""), "detail": detail,
        })

    db = get_sessionmaker()()
    try:
        profiles = list(db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )).all())
        profile_by_id = {int(row.id): row for row in profiles}
        student_no_counts = Counter(str(row.student_no).strip() for row in profiles if row.student_no)
        for student_no, count in student_no_counts.items():
            if count > 1:
                add("STUDENT", "DUPLICATE_STUDENT_NO", student_no, f"同租户有效主档 {count} 条")

        domain_models = (
            ("ACADEMIC", AcademicStudent), ("CAMPUS_SERVICE", CsServiceStudent),
            ("EMPLOYMENT", EmpStudent), ("GRADUATION", GraduationStudent),
            ("INTERNSHIP", InternshipRecord), ("ORIENTATION", OrientationStudent),
        )
        for domain, model in domain_models:
            rows = db.scalars(select(model).where(
                model.tenant_id == tenant_id, model.is_deleted.is_(False),
            )).all()
            for row in rows:
                student_id = getattr(row, "student_id", None)
                if not student_id:
                    add("STUDENT", "DOMAIN_STABLE_STUDENT_ID_MISSING", row.id,
                        f"{domain} 有效业务行未绑定 stable student_id")
                elif int(student_id) not in profile_by_id:
                    add("STUDENT", "DOMAIN_STUDENT_ORPHAN", row.id,
                        f"{domain}.student_id={student_id} 在本租户不存在")

        active_links = {int(value) for value in db.scalars(select(StudentAccountLink.user_id).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        )).all()}
        student_users = db.scalars(select(User).where(
            User.tenant_id == tenant_id, User.user_type == "STUDENT",
            User.status == "ACTIVE", User.is_deleted.is_(False),
        )).all()
        for user in student_users:
            if int(user.id) not in active_links:
                add("STUDENT", "ACCOUNT_LINK_MISSING", user.id,
                    f"真实学生账号 {user.login_name} 无 ACTIVE StudentAccountLink")

        buildings = {int(row.id): row for row in db.scalars(select(DormBuilding).where(
            DormBuilding.tenant_id == tenant_id, DormBuilding.is_deleted.is_(False),
        )).all()}
        rooms = {int(row.id): row for row in db.scalars(select(DormRoom).where(
            DormRoom.tenant_id == tenant_id, DormRoom.is_deleted.is_(False),
        )).all()}
        beds = list(db.scalars(select(DormBed).where(
            DormBed.tenant_id == tenant_id, DormBed.is_deleted.is_(False),
        )).all())
        beds_by_id = {int(row.id): row for row in beds}
        occupied_by_student = defaultdict(list)
        bed_count_by_room = Counter()
        for bed in beds:
            bed_count_by_room[int(bed.room_id)] += 1
            if bed.status == "OCCUPIED" and bed.student_id:
                occupied_by_student[int(bed.student_id)].append(bed)
            if bed.student_id and int(bed.student_id) not in profile_by_id:
                add("DORM", "BED_STUDENT_ORPHAN", bed.id,
                    f"bed.student_id={bed.student_id} 在本租户不存在")
            if int(bed.room_id) not in rooms or int(bed.building_id) not in buildings:
                add("DORM", "BED_RESOURCE_ORPHAN", bed.id, "床位指向不存在的房间或楼栋")
        for student_id, student_beds in occupied_by_student.items():
            if len(student_beds) > 1:
                add("DORM", "MULTIPLE_OCCUPIED_BEDS", student_id,
                    f"同一学生占用 {len(student_beds)} 个床位：{[row.id for row in student_beds]}")
        for room_id, room in rooms.items():
            actual = bed_count_by_room.get(room_id, 0)
            if int(room.capacity) != actual:
                add("DORM", "ROOM_CAPACITY_BED_COUNT_MISMATCH", room_id,
                    f"capacity={room.capacity}, 实际有效床位={actual}")

        active_stays = list(db.scalars(select(DormStay).where(
            DormStay.tenant_id == tenant_id, DormStay.status == "ACTIVE",
            DormStay.is_deleted.is_(False),
        )).all())
        stay_by_bed = defaultdict(list)
        stay_by_student = defaultdict(list)
        for stay in active_stays:
            stay_by_bed[int(stay.bed_id)].append(stay)
            stay_by_student[int(stay.student_id)].append(stay)
            bed = beds_by_id.get(int(stay.bed_id))
            if not bed or bed.status != "OCCUPIED" or int(bed.student_id or 0) != int(stay.student_id):
                add("DORM", "ACTIVE_STAY_BED_MISMATCH", stay.id,
                    f"ACTIVE Stay student={stay.student_id}, bed={stay.bed_id} 与当前床指针不一致")
        for bed in beds:
            if bed.status == "OCCUPIED":
                matches = stay_by_bed.get(int(bed.id), [])
                if len(matches) != 1:
                    add("DORM", "OCCUPIED_BED_ACTIVE_STAY_MISMATCH", bed.id,
                        f"OCCUPIED Bed 对应 ACTIVE Stay 数量={len(matches)}")
        for student_id, stays in stay_by_student.items():
            if len(stays) > 1:
                add("DORM", "MULTIPLE_ACTIVE_STAYS", student_id,
                    f"同一学生 ACTIVE Stay 数量={len(stays)}")

        cs_students = {int(row.id): row for row in db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == tenant_id, CsServiceStudent.is_deleted.is_(False),
        )).all()}
        active_cs_records = db.scalars(select(CsDormRecord).where(
            CsDormRecord.tenant_id == tenant_id, CsDormRecord.record_status == "ACTIVE",
            CsDormRecord.is_deleted.is_(False),
        )).all()
        for record in active_cs_records:
            cs = cs_students.get(int(record.cs_student_id or 0))
            if not cs or not cs.student_id:
                add("DORM", "CS_DORM_PROJECTION_STUDENT_UNRESOLVED", record.id,
                    f"CsDormRecord.cs_student_id={record.cs_student_id} 无法解析到稳定学生主档")
                continue
            stable_id = int(cs.student_id)
            current = occupied_by_student.get(stable_id, [])
            if len(current) != 1:
                add("DORM", "CS_DORM_PROJECTION_WITHOUT_CURRENT_BED", record.id,
                    f"CsDormRecord 对应当前床位数量={len(current)}")
                continue
            bed = current[0]
            room = rooms.get(int(bed.room_id))
            building = buildings.get(int(bed.building_id))
            expected = (building.building_name if building else "", room.room_no if room else "", bed.bed_no)
            actual = (record.building or "", record.room or "", record.bed or "")
            if expected != actual:
                add("DORM", "CS_DORM_PROJECTION_DRIFT", record.id,
                    f"投影={actual}，Authority={expected}")

        batches = {int(row.id): row for row in db.scalars(select(OrientationBatch).where(
            OrientationBatch.tenant_id == tenant_id, OrientationBatch.is_deleted.is_(False),
        )).all()}
        flow_versions = {int(row.id) for row in db.scalars(select(OrientationFlowVersion).where(
            OrientationFlowVersion.tenant_id == tenant_id,
            OrientationFlowVersion.is_deleted.is_(False),
        )).all()}
        orientation_rows = list(db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == tenant_id,
            OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.is_deleted.is_(False),
        )).all())
        for student in orientation_rows:
            batch = batches.get(int(student.batch_id or 0))
            if not batch:
                add("ORIENTATION", "ACTIVE_STUDENT_BATCH_MISSING", student.id,
                    f"batch_id={student.batch_id} 不存在")
                continue
            if not batch.flow_version_id or int(batch.flow_version_id) not in flow_versions:
                add("ORIENTATION", "FLOW_VERSION_MISSING", student.id,
                    f"批次 {batch.id} 的 flow_version_id={batch.flow_version_id} 不存在")
            else:
                required = set(db.scalars(select(OrientationFlowStep.step_key).where(
                    OrientationFlowStep.tenant_id == tenant_id,
                    OrientationFlowStep.flow_version_id == int(batch.flow_version_id),
                    OrientationFlowStep.enabled.is_(True), OrientationFlowStep.required.is_(True),
                    OrientationFlowStep.is_deleted.is_(False),
                )).all())
                actual = set(db.scalars(select(OrientationStudentStep.step_key).where(
                    OrientationStudentStep.tenant_id == tenant_id,
                    OrientationStudentStep.orientation_student_id == int(student.id),
                    OrientationStudentStep.is_deleted.is_(False),
                )).all())
                missing = sorted(required - actual)
                if missing:
                    add("ORIENTATION", "REQUIRED_STEP_RECORD_MISSING", student.id,
                        f"缺少冻结流程必办步骤：{missing}")
            if student.student_id:
                profile = profile_by_id.get(int(student.student_id))
                if not profile:
                    add("ORIENTATION", "STUDENT_ID_CROSS_TENANT_OR_ORPHAN", student.id,
                        f"student_id={student.student_id} 不属于本租户")
                current = occupied_by_student.get(int(student.student_id), [])
                if len(current) == 1:
                    bed = current[0]
                    room = rooms.get(int(bed.room_id))
                    building = buildings.get(int(bed.building_id))
                    expected = (building.building_name if building else "", room.room_no if room else "")
                    actual = (student.building or "", student.room or "")
                    if student.dorm_status in ("ASSIGNED", "CHECKED_IN") and actual != expected:
                        add("ORIENTATION", "DORM_PROJECTION_DRIFT", student.id,
                            f"迎新住宿投影={actual}，Dorm Authority={expected}")
                elif student.dorm_status == "CHECKED_IN":
                    add("ORIENTATION", "DORM_PROJECTION_WITHOUT_ACTIVE_BED", student.id,
                        "迎新投影为已入住，但没有唯一 OCCUPIED Bed")

        # 资格投影只做无写重算；hash 不同即报告漂移，绝不在审计脚本中修正。
        from app.services.orientation_qualification_service import evaluate
        decisions = {int(row.orientation_student_id): row for row in db.scalars(select(
            OrientationQualificationDecision,
        ).where(
            OrientationQualificationDecision.tenant_id == tenant_id,
            OrientationQualificationDecision.is_deleted.is_(False),
        )).all()}
        for student in orientation_rows:
            decision = decisions.get(int(student.id))
            try:
                calculated = evaluate(db, student, persist=False)
            except Exception as exc:  # 只报告异常，绝不因此进入修复分支
                add("ORIENTATION", "QUALIFICATION_RECALCULATION_FAILED", student.id,
                    f"无写重算失败：{type(exc).__name__}: {exc}")
                continue
            if decision and decision.input_hash != calculated["inputHash"]:
                add("ORIENTATION", "QUALIFICATION_PROJECTION_DRIFT", student.id,
                    f"stored={decision.input_hash[:12]}..., current={calculated['inputHash'][:12]}...")
    finally:
        db.rollback()
        db.close()
        set_tenant(None)

    counts = Counter(issue["domain"] for issue in issues)
    return {
        "tenantId": str(tenant_id), "readOnly": True,
        "issueCount": len(issues), "countsByDomain": dict(sorted(counts.items())),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="只读审计全校 Authority 一致性")
    parser.add_argument("--tenant-id", required=True, type=int)
    parser.add_argument("--output", type=Path, help="可选 JSON 报告路径")
    args = parser.parse_args()
    set_tenant(args.tenant_id)
    try:
        report = audit(args.tenant_id)
    finally:
        set_tenant(None)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["issueCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
