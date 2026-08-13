"""sandbox-school · 20K 真实学校 13A 学工高频数据。

目标不是“所有表塞一条”，而是按真实职业院校场景生成可解释的发生率与跨表关系：
- 住宿：真实 楼栋→楼层→房间→床位→学生，占用事实与 t_cs_dorm_record 对账；
- 班级：班干部、班会/学期总结材料；
- 辅导员：按真实所带班级/学生数形成学期考评；
- 学生工作：谈心谈话、家校联系、困难认定、助学金、少量违纪处分；
- 风险：只引用已经存在的学业/宿舍/实习真实来源单据。

敏感字段严格走 field_crypto；不复制真实学校/真实个人信息，不使用 generic marker ID。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.field_crypto import encrypt_sensitive
from app.services.sandbox_school_master_seed import _bulk_insert

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)

EXPECTED_DORM_BUILDINGS = 12
EXPECTED_DORM_ROOMS = 2016       # 12 栋 × 7 层 × 24 间
EXPECTED_DORM_BEDS = 12096       # 每间 6 床
EXPECTED_OCCUPIED_BEDS = 11050   # 与 core domain 的 85% 住宿口径一致
EXPECTED_CLASS_CADRES = 768      # 2024/2025 两届 256 班 × 3
EXPECTED_CLASS_MATERIALS = 512   # 256 班 × 2 条历史材料
EXPECTED_COUNSELOR_ASSESSMENTS = 192
EXPECTED_TALKS = 650             # 13,000 老生约 5%
EXPECTED_FAMILY_CONTACTS = 162
EXPECTED_AID_APPROVED = 1560     # 13,000 老生约 12%
EXPECTED_FUNDING_GRANTED = 1300
EXPECTED_DISCIPLINE_CASES = 80
EXPECTED_EFFECTIVE_DISCIPLINE = 50
EXPECTED_AFFAIRS_RISKS = 300

MALE_BUILDINGS = tuple(f"崇德苑{i}栋" for i in range(1, 7))
FEMALE_BUILDINGS = tuple(f"明德苑{i}栋" for i in range(1, 7))


def _returning_roster(db, tenant_id: int) -> list[dict]:
    from app.models import SchoolClass, StudentProfile

    rows = db.execute(
        select(
            StudentProfile.id,
            StudentProfile.student_no,
            StudentProfile.real_name,
            StudentProfile.gender,
            StudentProfile.grade,
            StudentProfile.class_id,
            SchoolClass.class_name,
            SchoolClass.counselor_id,
        )
        .join(SchoolClass, SchoolClass.id == StudentProfile.class_id)
        .where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade.in_(("2024", "2025")),
            StudentProfile.is_deleted.is_(False),
            SchoolClass.is_deleted.is_(False),
        )
        .order_by(StudentProfile.student_no)
    ).all()
    return [{
        "id": int(r.id),
        "student_no": r.student_no,
        "name": r.real_name,
        "gender": r.gender,
        "grade": str(r.grade),
        "class_id": int(r.class_id),
        "class_name": r.class_name,
        "counselor_id": int(r.counselor_id) if r.counselor_id else None,
    } for r in rows]


def _spread(items: list[dict], count: int) -> list[dict]:
    """在整个人群中均匀取样，避免所有业务都集中在前几个班。"""
    if count <= 0 or not items:
        return []
    if count > len(items):
        raise ValueError("sample count exceeds population")
    return [items[(idx * len(items)) // count] for idx in range(count)]


def _seed_dorm_inventory(db, tenant_id: int) -> dict:
    from app.models import (CsDormRecord, CsServiceStudent, DormBed, DormBuilding,
                            DormRoom)

    building_rows = []
    for idx, name in enumerate(MALE_BUILDINGS, 1):
        building_rows.append({
            "tenant_id": tenant_id,
            "building_name": name,
            "building_code": f"M{idx:02d}",
            "gender_limit": "MALE",
            "manager_teacher_key": f"sbx_sa{((idx - 1) % 32) + 1:03d}",
            "floor_count": 7,
            "status": "ENABLED",
        })
    for idx, name in enumerate(FEMALE_BUILDINGS, 1):
        building_rows.append({
            "tenant_id": tenant_id,
            "building_name": name,
            "building_code": f"F{idx:02d}",
            "gender_limit": "FEMALE",
            "manager_teacher_key": f"sbx_sa{((idx + 5) % 32) + 1:03d}",
            "floor_count": 7,
            "status": "ENABLED",
        })
    _bulk_insert(db, DormBuilding, building_rows)
    db.flush()
    buildings = list(db.execute(select(
        DormBuilding.id, DormBuilding.building_code, DormBuilding.building_name,
        DormBuilding.gender_limit,
    ).where(
        DormBuilding.tenant_id == tenant_id,
        DormBuilding.is_deleted.is_(False),
    ).order_by(DormBuilding.building_code)).all())

    room_rows = []
    for building in buildings:
        for floor_no in range(1, 8):
            for room_seq in range(1, 25):
                room_no = f"{floor_no}{room_seq:02d}"
                room_rows.append({
                    "tenant_id": tenant_id,
                    "building_id": int(building.id),
                    "floor_no": floor_no,
                    "room_no": room_no,
                    "capacity": 6,
                    "room_type": "STANDARD_6",
                    "status": "ENABLED",
                })
    _bulk_insert(db, DormRoom, room_rows, chunk_size=1000)
    db.flush()
    rooms = list(db.execute(select(
        DormRoom.id, DormRoom.building_id, DormRoom.floor_no, DormRoom.room_no,
    ).where(
        DormRoom.tenant_id == tenant_id,
        DormRoom.is_deleted.is_(False),
    ).order_by(DormRoom.building_id, DormRoom.floor_no, DormRoom.room_no)).all())
    building_meta = {int(x.id): x for x in buildings}
    rooms_by_gender = {"男": [], "女": []}
    for room in rooms:
        meta = building_meta[int(room.building_id)]
        key = "男" if meta.gender_limit == "MALE" else "女"
        rooms_by_gender[key].append((room, meta))

    boarders = list(db.execute(
        select(
            CsDormRecord.id,
            CsDormRecord.cs_student_id,
            CsServiceStudent.student_id,
            CsServiceStudent.gender,
        )
        .join(CsServiceStudent, CsServiceStudent.id == CsDormRecord.cs_student_id)
        .where(
            CsDormRecord.tenant_id == tenant_id,
            CsDormRecord.is_deleted.is_(False),
            CsServiceStudent.tenant_id == tenant_id,
            CsServiceStudent.is_deleted.is_(False),
        )
        .order_by(CsServiceStudent.gender, CsDormRecord.id)
    ).all()
    if len(boarders) != EXPECTED_OCCUPIED_BEDS:
        raise RuntimeError(f"住宿生基数不符: {len(boarders)} != {EXPECTED_OCCUPIED_BEDS}")

    boarders_by_gender = {"男": [], "女": []}
    for row in boarders:
        if row.gender not in boarders_by_gender:
            raise RuntimeError(f"无法分配宿舍的性别值: {row.gender!r}")
        boarders_by_gender[row.gender].append(row)

    # 每个性别 6 栋 × 7 层 × 24 间 × 6 床 = 6048，足够容纳约 5525 人。
    for gender, people in boarders_by_gender.items():
        if len(people) > len(rooms_by_gender[gender]) * 6:
            raise RuntimeError(f"{gender}生宿舍容量不足")

    update_rows = []
    bed_rows = []
    for gender in ("男", "女"):
        people = boarders_by_gender[gender]
        person_idx = 0
        for room, building in rooms_by_gender[gender]:
            for bed_seq in range(1, 7):
                occupied = person_idx < len(people)
                person = people[person_idx] if occupied else None
                bed_no = f"{room.room_no}-{bed_seq}"
                bed_rows.append({
                    "tenant_id": tenant_id,
                    "building_id": int(building.id),
                    "room_id": int(room.id),
                    "bed_no": bed_no,
                    "student_id": int(person.student_id) if person else None,
                    "occupied_at": datetime(2025, 9, 1, 10, 0) if person else None,
                    "cs_dorm_record_id": int(person.id) if person else None,
                    "status": "OCCUPIED" if person else "VACANT",
                })
                if person:
                    update_rows.append({
                        "id": int(person.id),
                        "building": building.building_name,
                        "room": room.room_no,
                        "bed": str(bed_seq),
                    })
                    person_idx += 1
        if person_idx != len(people):
            raise RuntimeError(f"{gender}生宿舍分配未完成: {person_idx}/{len(people)}")

    _bulk_insert(db, DormBed, bed_rows, chunk_size=1000)
    # SQLAlchemy bulk_update_mappings 会按主键批量更新，避免 11k 次 flush。
    db.bulk_update_mappings(CsDormRecord, update_rows)
    db.commit()

    occupied = int(db.scalar(select(func.count()).select_from(DormBed).where(
        DormBed.tenant_id == tenant_id,
        DormBed.status == "OCCUPIED",
        DormBed.is_deleted.is_(False),
    )) or 0)
    return {
        "buildings": len(building_rows),
        "rooms": len(room_rows),
        "beds": len(bed_rows),
        "occupiedBeds": occupied,
        "vacantBeds": len(bed_rows) - occupied,
    }


def _seed_class_and_counselor(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import (AffairsClassCadre, AffairsClassMaterial,
                            AffairsCounselorAssessment,
                            AffairsCounselorAssessmentPeriod, SchoolClass, User)

    by_class: dict[int, list[dict]] = {}
    for stu in roster:
        by_class.setdefault(stu["class_id"], []).append(stu)

    cadre_rows = []
    material_rows = []
    positions = ("MONITOR", "LEAGUE_SECRETARY", "STUDY")
    for class_id, students in sorted(by_class.items()):
        for pos, stu in zip(positions, students[:3]):
            cadre_rows.append({
                "tenant_id": tenant_id,
                "class_id": class_id,
                "student_id": stu["id"],
                "position": pos,
                "term_code": "2025-2026-2",
                "appointed_at": datetime(2025, 9, 12, 14, 0),
                "status": "ACTIVE",
                "record_status": "ACTIVE",
            })
        material_rows.extend((
            {
                "tenant_id": tenant_id,
                "class_id": class_id,
                "material_type": "CLASS_MEETING",
                "title": "期末安全教育与暑期安排主题班会记录",
                "material_at": datetime(2026, 6, 25, 16, 0),
                "remark": "完成暑期安全、实习准备和返校事项提醒，线上保留班级工作台账。",
                "uploader": students[0].get("name") or "班级负责人",
                "status": "ACTIVE",
            },
            {
                "tenant_id": tenant_id,
                "class_id": class_id,
                "material_type": "SUMMARY",
                "title": "2025-2026学年第二学期班级工作总结",
                "material_at": datetime(2026, 7, 3, 10, 0),
                "remark": "汇总班级学业、日常管理、资助帮扶与重点学生跟进情况。",
                "uploader": students[0].get("name") or "班级负责人",
                "status": "ACTIVE",
            },
        ))
    _bulk_insert(db, AffairsClassCadre, cadre_rows, chunk_size=1000)
    _bulk_insert(db, AffairsClassMaterial, material_rows, chunk_size=1000)

    period = AffairsCounselorAssessmentPeriod(
        tenant_id=tenant_id,
        period_name="2025-2026学年第二学期辅导员工作考评",
        semester="2025-2026-2",
        status="PUBLISHED",
        remark="依据班级管理、谈心谈话、风险处置、资助与宿舍工作量形成历史学期考评。",
    )
    db.add(period)
    db.flush()

    class_stats = db.execute(
        select(
            SchoolClass.counselor_id,
            func.count(func.distinct(SchoolClass.id)).label("class_count"),
            func.count().label("student_count"),
        )
        .join(__import__("app.models", fromlist=["StudentProfile"]).StudentProfile,
              __import__("app.models", fromlist=["StudentProfile"]).StudentProfile.class_id == SchoolClass.id)
        .where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.grade.in_(("2024", "2025")),
            SchoolClass.counselor_id.is_not(None),
            SchoolClass.is_deleted.is_(False),
            __import__("app.models", fromlist=["StudentProfile"]).StudentProfile.is_deleted.is_(False),
        )
        .group_by(SchoolClass.counselor_id)
    ).all()
    counselor_ids = [int(x.counselor_id) for x in class_stats]
    names = {
        int(uid): name for uid, name in db.execute(select(User.id, User.real_name).where(
            User.tenant_id == tenant_id,
            User.id.in_(counselor_ids),
            User.is_deleted.is_(False),
        )).all()
    }
    assessment_rows = []
    ranked = []
    for idx, stat in enumerate(class_stats, 1):
        auto = Decimal(str(82 + (idx % 13)))
        college = Decimal(str(80 + ((idx * 3) % 16)))
        total = (auto * Decimal("0.6") + college * Decimal("0.4")).quantize(Decimal("0.1"))
        ranked.append((total, stat, auto, college))
    ranked.sort(key=lambda x: x[0], reverse=True)
    for rank_no, (total, stat, auto, college) in enumerate(ranked, 1):
        uid = int(stat.counselor_id)
        assessment_rows.append({
            "tenant_id": tenant_id,
            "period_id": int(period.id),
            "counselor_id": uid,
            "counselor_name": names.get(uid, "辅导员"),
            "class_count": int(stat.class_count),
            "student_count": int(stat.student_count),
            "metrics_json": json.dumps({
                "studentCoverage": int(stat.student_count),
                "classCount": int(stat.class_count),
                "talkRecords": 3 + rank_no % 6,
                "riskClosures": rank_no % 5,
                "familyContacts": 1 + rank_no % 4,
            }, ensure_ascii=False),
            "auto_score": auto,
            "college_score": college,
            "total_score": total,
            "rank_no": rank_no,
            "status": "SCORED",
            "scored_by": "学生工作处",
            "scored_at": datetime(2026, 7, 10, 10, 0),
        })
    _bulk_insert(db, AffairsCounselorAssessment, assessment_rows, chunk_size=500)
    db.commit()
    return {
        "cadres": len(cadre_rows),
        "classMaterials": len(material_rows),
        "assessmentPeriods": 1,
        "counselorAssessments": len(assessment_rows),
    }


def _seed_talks_and_family(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import FamilyContactLog, TalkRecord

    talks = _spread(roster, EXPECTED_TALKS)
    talk_rows = []
    for idx, stu in enumerate(talks, 1):
        topic_type = ("ACADEMIC", "DAILY", "DORM", "INTERNSHIP")[idx % 4]
        need_follow = idx % 5 == 0
        status = "FOLLOW_UP" if need_follow else ("COMPLETED" if idx % 7 == 0 else "CLOSED")
        topic = {
            "ACADEMIC": "期末成绩与下学期学习计划",
            "DAILY": "暑期生活与返校准备",
            "DORM": "宿舍生活与安全习惯",
            "INTERNSHIP": "岗位实习准备与职业适应",
        }[topic_type]
        talk_rows.append({
            "tenant_id": tenant_id,
            "student_id": stu["id"],
            "teacher_id": stu["counselor_id"],
            "topic_type": topic_type,
            "topic": topic,
            "talk_at": datetime(2026, 6, 1, 14, 0) + timedelta(hours=idx % 240),
            "content": "围绕学生当前学习生活状态、暑期安排和下一阶段目标进行常规谈话，并确认需要继续跟进的事项。",
            "result": "NEED_FOLLOW" if need_follow else "NORMAL",
            "need_follow": need_follow,
            "status": status,
        })
    _bulk_insert(db, TalkRecord, talk_rows, chunk_size=1000)

    family_rows = []
    for idx, stu in enumerate(talks, 1):
        if idx % 4:
            continue
        family_rows.append({
            "tenant_id": tenant_id,
            "student_id": stu["id"],
            "teacher_id": stu["counselor_id"],
            "contact_type": "PHONE" if idx % 8 else "WECHAT",
            "contact_reason": "学期末学习生活情况沟通与暑期安全提醒",
            "contact_result": "家长已了解学生在校情况，并确认保持必要沟通。",
            "full_phone_viewed": False,
            "occurred_at": datetime(2026, 6, 20, 18, 0) + timedelta(minutes=idx),
            "receipt_status": "RECEIVED" if idx % 12 else "PENDING",
            "receipt_at": datetime(2026, 6, 21, 9, 0) if idx % 12 else None,
            "receipt_note": "已知悉学校提醒" if idx % 12 else None,
        })
    _bulk_insert(db, FamilyContactLog, family_rows, chunk_size=500)
    db.commit()
    return {"talkRecords": len(talk_rows), "familyContacts": len(family_rows)}


def _seed_aid_and_funding(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import (AidApply, AidBatch, AidFamilyEconomy, AidLevelHistory,
                            FundingApplication, FundingBatch, FundingDisbursement,
                            FundingProject)

    historical = AidBatch(
        tenant_id=tenant_id,
        batch_name="2025-2026学年家庭经济困难学生认定",
        year_code="2025-2026",
        apply_start=datetime(2025, 9, 5),
        apply_end=datetime(2025, 9, 20),
        publicity_days=5,
        level_config_json=json.dumps({"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]}),
        scope_json=json.dumps({"grades": ["2024", "2025"]}),
        status="CLOSED",
    )
    current = AidBatch(
        tenant_id=tenant_id,
        batch_name="2026-2027学年家庭经济困难学生认定",
        year_code="2026-2027",
        apply_start=datetime(2026, 9, 10),
        apply_end=datetime(2026, 9, 25),
        publicity_days=5,
        level_config_json=json.dumps({"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]}),
        scope_json=json.dumps({"grades": ["2024", "2025", "2026"]}),
        status="DRAFT",
    )
    db.add_all([historical, current])
    db.flush()

    aid_students = _spread(roster, EXPECTED_AID_APPROVED)
    apply_rows = []
    for idx, stu in enumerate(aid_students, 1):
        level = "SPECIAL" if idx % 20 == 0 else ("DIFFICULT" if idx % 4 == 0 else "GENERAL")
        apply_rows.append({
            "tenant_id": tenant_id,
            "batch_id": int(historical.id),
            "student_id": stu["id"],
            "apply_level": level,
            "suggest_level": level,
            "final_level": level,
            "statement": "家庭收入来源较少，教育与生活支出压力较大，按学校要求提交困难认定材料。",
            "class_review_score": Decimal(str(78 + idx % 20)),
            "class_review_rank": 1 + idx % 15,
            "status": "APPROVED",
            "publicity_at": datetime(2025, 10, 10, 9, 0),
            "result_at": datetime(2025, 10, 18, 10, 0),
        })
    _bulk_insert(db, AidApply, apply_rows, chunk_size=500)
    db.flush()
    applications = list(db.execute(select(
        AidApply.id, AidApply.student_id, AidApply.final_level,
    ).where(
        AidApply.tenant_id == tenant_id,
        AidApply.batch_id == historical.id,
        AidApply.status == "APPROVED",
        AidApply.is_deleted.is_(False),
    ).order_by(AidApply.id)).all())

    economy_rows = []
    history_rows = []
    for idx, app in enumerate(applications, 1):
        income = 18000 + (idx % 120) * 300
        debt = 0 if idx % 5 else 5000 + (idx % 20) * 500
        flags = []
        if idx % 20 == 0:
            flags.append("低保")
        if idx % 37 == 0:
            flags.append("残疾家庭成员")
        economy_rows.append({
            "tenant_id": tenant_id,
            "apply_id": int(app.id),
            "student_id": int(app.student_id),
            "member_count": 3 + idx % 4,
            "income_encrypted": encrypt_sensitive(str(income), "family_income"),
            "debt_encrypted": encrypt_sensitive(str(debt), "family_debt") if debt else None,
            "special_flags_json": json.dumps(flags, ensure_ascii=False),
        })
        history_rows.append({
            "tenant_id": tenant_id,
            "student_id": int(app.student_id),
            "from_level": None,
            "to_level": app.final_level,
            "change_type": "IDENTIFY",
            "apply_id": int(app.id),
            "batch_id": int(historical.id),
            "year_code": "2025-2026",
            "effective_at": datetime(2025, 10, 18, 10, 0),
        })
    _bulk_insert(db, AidFamilyEconomy, economy_rows, chunk_size=500)
    _bulk_insert(db, AidLevelHistory, history_rows, chunk_size=500)

    project = FundingProject(
        tenant_id=tenant_id,
        project_name="国家助学金",
        project_type="GRANT",
        amount=Decimal("3300.00"),
        quota=1500,
        condition_json=json.dumps({"requireDifficultLibrary": True}, ensure_ascii=False),
        status="ENABLED",
    )
    db.add(project)
    db.flush()
    historical_funding = FundingBatch(
        tenant_id=tenant_id,
        project_id=int(project.id),
        project_type="GRANT",
        year_code="2025-2026",
        apply_start=datetime(2025, 10, 20),
        apply_end=datetime(2025, 11, 5),
        publicity_days=5,
        quota=EXPECTED_FUNDING_GRANTED,
        amount_budget=Decimal("4290000.00"),
        reserved_quota=EXPECTED_FUNDING_GRANTED,
        reserved_amount=Decimal("4290000.00"),
        status="CLOSED",
    )
    current_funding = FundingBatch(
        tenant_id=tenant_id,
        project_id=int(project.id),
        project_type="GRANT",
        year_code="2026-2027",
        apply_start=datetime(2026, 10, 10),
        apply_end=datetime(2026, 10, 25),
        publicity_days=5,
        quota=1500,
        amount_budget=Decimal("4950000.00"),
        reserved_quota=0,
        reserved_amount=Decimal("0.00"),
        status="DRAFT",
    )
    db.add_all([historical_funding, current_funding])
    db.flush()

    funding_students = applications[:EXPECTED_FUNDING_GRANTED]
    funding_rows = []
    for app in funding_students:
        funding_rows.append({
            "tenant_id": tenant_id,
            "batch_id": int(historical_funding.id),
            "student_id": int(app.student_id),
            "apply_source": "SELF",
            "project_type": "GRANT",
            "amount": Decimal("3300.00"),
            "requested_amount": Decimal("3300.00"),
            "approved_amount": Decimal("3300.00"),
            "approved_at": datetime(2025, 11, 25, 10, 0),
            "quota_reserved": True,
            "statement": "已完成困难认定，申请国家助学金支持在校学习生活。",
            "check_snapshot_json": json.dumps({"difficultLibrary": True, "schoolStatus": "ACTIVE"}),
            "status": "GRANTED",
            "publicity_at": datetime(2025, 11, 18, 9, 0),
            "result_at": datetime(2025, 11, 25, 10, 0),
        })
    _bulk_insert(db, FundingApplication, funding_rows, chunk_size=500)
    db.flush()
    granted = list(db.execute(select(
        FundingApplication.id, FundingApplication.student_id, FundingApplication.approved_amount,
        FundingApplication.approved_at, FundingApplication.version,
    ).where(
        FundingApplication.tenant_id == tenant_id,
        FundingApplication.batch_id == historical_funding.id,
        FundingApplication.status == "GRANTED",
        FundingApplication.is_deleted.is_(False),
    ).order_by(FundingApplication.id)).all())
    disbursement_rows = []
    for idx, row in enumerate(granted, 1):
        disbursement_rows.append({
            "tenant_id": tenant_id,
            "application_id": int(row.id),
            "batch_id": int(historical_funding.id),
            "student_id": int(row.student_id),
            "project_type": "GRANT",
            "amount": row.approved_amount,
            "approved_amount_snapshot": row.approved_amount,
            "approved_at_snapshot": row.approved_at,
            "approval_version_snapshot": int(row.version or 0),
            "disburse_no": "GRANT-2025-2026-01",
            "bank_last4": f"{1000 + (idx % 9000):04d}",
            "bank_status": "ISSUED",
            "issued_at": datetime(2025, 12, 10, 9, 0),
        })
    _bulk_insert(db, FundingDisbursement, disbursement_rows, chunk_size=500)
    db.commit()
    return {
        "aidBatches": 2,
        "aidApproved": len(apply_rows),
        "aidSensitiveProfiles": len(economy_rows),
        "fundingProjects": 1,
        "fundingBatches": 2,
        "fundingGranted": len(funding_rows),
        "fundingIssued": len(disbursement_rows),
    }


def _seed_discipline(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import CsDiscipline, CsServiceStudent, DisciplineCase

    selected = _spread(roster, EXPECTED_DISCIPLINE_CASES)
    cases = []
    for idx, stu in enumerate(selected, 1):
        effective = idx <= EXPECTED_EFFECTIVE_DISCIPLINE
        cases.append(DisciplineCase(
            tenant_id=tenant_id,
            student_id=stu["id"],
            disc_type="WARNING" if idx % 5 else "SERIOUS_WARNING",
            reason="违反宿舍晚归管理规定，经教育提醒后按学生管理规定登记处理。",
            doc_no=f"跃科职院学处〔2026〕{idx:03d}号" if effective else None,
            decide_date=datetime(2026, 4, 15) if effective else None,
            effective_at=datetime(2026, 4, 18) if effective else None,
            status="EFFECTIVE" if effective else "REGISTERED",
            delivered_at=datetime(2026, 4, 19) if effective else None,
            delivery_method="DIRECT" if effective else None,
            delivery_remark="已向学生本人送达并完成签收" if effective else None,
        ))
    db.add_all(cases)
    db.flush()

    cs_map = {
        int(student_id): int(csid)
        for csid, student_id in db.execute(select(CsServiceStudent.id, CsServiceStudent.student_id).where(
            CsServiceStudent.tenant_id == tenant_id,
            CsServiceStudent.is_deleted.is_(False),
        )).all()
    }
    projections = []
    for idx, case in enumerate(cases[:EXPECTED_EFFECTIVE_DISCIPLINE], 1):
        csid = cs_map.get(int(case.student_id))
        if not csid:
            raise RuntimeError(f"处分投影缺少 CsServiceStudent: student={case.student_id}")
        row = CsDiscipline(
            tenant_id=tenant_id,
            cs_student_id=csid,
            code=f"DISC-2026-{idx:03d}",
            disc_type=case.disc_type,
            reason=case.reason,
            decide_date=case.decide_date,
            doc_no=case.doc_no,
            status="EFFECTIVE",
            record_status="ACTIVE",
            source_case_id=int(case.id),
        )
        db.add(row)
        db.flush()
        case.cs_discipline_id = int(row.id)
        projections.append(row)
    db.commit()
    return {"disciplineCases": len(cases), "effectiveProjections": len(projections)}


def _seed_risk_hub(db, tenant_id: int) -> dict:
    from app.models import (AcademicStudent, AcademicWarning, AffairsRiskRecord,
                            CsDormException, CsServiceStudent, InternshipRecord,
                            RiskRecord, SchoolClass, StudentProfile)

    candidates: list[dict] = []
    academic = db.execute(
        select(AcademicWarning.id, AcademicStudent.student_id)
        .join(AcademicStudent, AcademicStudent.id == AcademicWarning.acad_student_id)
        .where(
            AcademicWarning.tenant_id == tenant_id,
            AcademicWarning.status == "PENDING_HANDLE",
            AcademicWarning.is_deleted.is_(False),
            AcademicStudent.is_deleted.is_(False),
        )
        .order_by(AcademicWarning.id)
        .limit(150)
    ).all()
    candidates.extend({"source": "ACADEMIC_WARNING", "ref": int(r.id), "student_id": int(r.student_id),
                       "title": "学业预警待辅导员跟进"} for r in academic)

    dorm = db.execute(
        select(CsDormException.id, CsServiceStudent.student_id)
        .join(CsServiceStudent, CsServiceStudent.id == CsDormException.cs_student_id)
        .where(
            CsDormException.tenant_id == tenant_id,
            CsDormException.status.in_(("PENDING_HANDLE", "PROCESSING")),
            CsDormException.is_deleted.is_(False),
            CsServiceStudent.is_deleted.is_(False),
        )
        .order_by(CsDormException.id)
        .limit(75)
    ).all()
    candidates.extend({"source": "DORM", "ref": int(r.id), "student_id": int(r.student_id),
                       "title": "宿舍异常需要跟进核实"} for r in dorm)

    internship = db.execute(
        select(RiskRecord.id, InternshipRecord.student_id)
        .join(InternshipRecord, InternshipRecord.id == RiskRecord.internship_id)
        .where(
            RiskRecord.tenant_id == tenant_id,
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
            RiskRecord.is_deleted.is_(False),
            InternshipRecord.is_deleted.is_(False),
        )
        .order_by(RiskRecord.id)
        .limit(75)
    ).all()
    candidates.extend({"source": "INTERNSHIP", "ref": int(r.id), "student_id": int(r.student_id),
                       "title": "岗位实习风险需要继续处置"} for r in internship)

    if len(candidates) < EXPECTED_AFFAIRS_RISKS:
        # 来源数据不足时不造假：直接失败，要求上游真实业务事实先补齐。
        raise RuntimeError(f"学工风险真实来源不足: {len(candidates)}/{EXPECTED_AFFAIRS_RISKS}")
    candidates = candidates[:EXPECTED_AFFAIRS_RISKS]

    student_ids = [x["student_id"] for x in candidates]
    owner_by_student = {
        int(sid): int(counselor_id)
        for sid, counselor_id in db.execute(
            select(StudentProfile.id, SchoolClass.counselor_id)
            .join(SchoolClass, SchoolClass.id == StudentProfile.class_id)
            .where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.id.in_(student_ids),
                SchoolClass.counselor_id.is_not(None),
            )
        ).all()
    }
    rows = []
    for idx, item in enumerate(candidates, 1):
        rows.append({
            "tenant_id": tenant_id,
            "student_id": item["student_id"],
            "source": item["source"],
            "source_ref_id": item["ref"],
            "risk_level": "HIGH" if idx % 20 == 0 else "MEDIUM",
            "title": item["title"],
            "detail": "风险来源保留在原业务单据，本中枢只做引用、责任分派与跟进。",
            "owner_id": owner_by_student.get(item["student_id"]),
            "deadline_at": REFERENCE_NOW + timedelta(days=5),
            "assigned_at": REFERENCE_NOW - timedelta(days=1),
            "status": "PROCESSING" if idx % 3 == 0 else "ASSIGNED",
            "is_archived": False,
        })
    _bulk_insert(db, AffairsRiskRecord, rows, chunk_size=500)
    db.commit()
    return {"riskRecords": len(rows)}


def validate_affairs_facts(db, tenant_id: int) -> dict:
    from app.models import (AidApply, AffairsClassCadre, AffairsClassMaterial,
                            AffairsCounselorAssessment, AffairsRiskRecord,
                            DisciplineCase, DormBed, DormBuilding, DormRoom,
                            FamilyContactLog, FundingApplication,
                            FundingDisbursement, TalkRecord)

    def count(model, *conditions):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *conditions,
        )) or 0)

    report = {
        "dormBuildings": count(DormBuilding, DormBuilding.is_deleted.is_(False)),
        "dormRooms": count(DormRoom, DormRoom.is_deleted.is_(False)),
        "dormBeds": count(DormBed, DormBed.is_deleted.is_(False)),
        "occupiedBeds": count(DormBed, DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False)),
        "classCadres": count(AffairsClassCadre, AffairsClassCadre.status == "ACTIVE", AffairsClassCadre.is_deleted.is_(False)),
        "classMaterials": count(AffairsClassMaterial, AffairsClassMaterial.status == "ACTIVE", AffairsClassMaterial.is_deleted.is_(False)),
        "counselorAssessments": count(AffairsCounselorAssessment, AffairsCounselorAssessment.is_deleted.is_(False)),
        "talkRecords": count(TalkRecord, TalkRecord.is_deleted.is_(False)),
        "familyContacts": count(FamilyContactLog),
        "aidApproved": count(AidApply, AidApply.status == "APPROVED", AidApply.is_deleted.is_(False)),
        "fundingGranted": count(FundingApplication, FundingApplication.status == "GRANTED", FundingApplication.is_deleted.is_(False)),
        "fundingIssued": count(FundingDisbursement, FundingDisbursement.bank_status == "ISSUED", FundingDisbursement.is_deleted.is_(False)),
        "disciplineCases": count(DisciplineCase, DisciplineCase.is_deleted.is_(False)),
        "effectiveDiscipline": count(DisciplineCase, DisciplineCase.status == "EFFECTIVE", DisciplineCase.is_deleted.is_(False)),
        "riskRecords": count(AffairsRiskRecord, AffairsRiskRecord.is_deleted.is_(False)),
    }
    expected = {
        "dormBuildings": EXPECTED_DORM_BUILDINGS,
        "dormRooms": EXPECTED_DORM_ROOMS,
        "dormBeds": EXPECTED_DORM_BEDS,
        "occupiedBeds": EXPECTED_OCCUPIED_BEDS,
        "classCadres": EXPECTED_CLASS_CADRES,
        "classMaterials": EXPECTED_CLASS_MATERIALS,
        "counselorAssessments": EXPECTED_COUNSELOR_ASSESSMENTS,
        "talkRecords": EXPECTED_TALKS,
        "familyContacts": EXPECTED_FAMILY_CONTACTS,
        "aidApproved": EXPECTED_AID_APPROVED,
        "fundingGranted": EXPECTED_FUNDING_GRANTED,
        "fundingIssued": EXPECTED_FUNDING_GRANTED,
        "disciplineCases": EXPECTED_DISCIPLINE_CASES,
        "effectiveDiscipline": EXPECTED_EFFECTIVE_DISCIPLINE,
        "riskRecords": EXPECTED_AFFAIRS_RISKS,
    }
    mismatch = {k: {"expected": expected[k], "actual": report[k]} for k in expected if expected[k] != report[k]}
    if mismatch:
        raise RuntimeError(f"20K 学工数据验收失败: {mismatch}")

    # 宿舍唯一占用关系：每个住宿生恰好一张 OCCUPIED 床。
    occupied_students = int(db.scalar(select(func.count(func.distinct(DormBed.student_id))).where(
        DormBed.tenant_id == tenant_id,
        DormBed.status == "OCCUPIED",
        DormBed.student_id.is_not(None),
        DormBed.is_deleted.is_(False),
    )) or 0)
    if occupied_students != EXPECTED_OCCUPIED_BEDS:
        raise RuntimeError(f"宿舍床位重复占用: distinctStudents={occupied_students}")
    report["distinctOccupiedStudents"] = occupied_students
    report["passed"] = True
    return report


def seed_school_affairs_20k(db, tenant_id: int) -> dict:
    roster = _returning_roster(db, tenant_id)
    if len(roster) != 13_000:
        raise RuntimeError(f"13A 老生基数应为 13000，实际 {len(roster)}")
    result = {
        "dorm": _seed_dorm_inventory(db, tenant_id),
        "classAndCounselor": _seed_class_and_counselor(db, tenant_id, roster),
        "talkAndFamily": _seed_talks_and_family(db, tenant_id, roster),
        "aidAndFunding": _seed_aid_and_funding(db, tenant_id, roster),
        "discipline": _seed_discipline(db, tenant_id, roster),
        "riskHub": _seed_risk_hub(db, tenant_id),
    }
    result["validation"] = validate_affairs_facts(db, tenant_id)
    return result
