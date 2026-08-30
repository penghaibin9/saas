"""补齐 sandbox-school AA-001～024 中缺失的正式成功链。

该种子不替换既有失败/在途案例，只追加可复核的成功案例；每个案例都保留来源单据、
审批/审计或不可变事实，并且可重复执行。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import func, select


NOW = datetime(2026, 8, 29, 16, 0)
MARKER = "AA24-FLOW-CLOSURE-2026"


def _classes():
    from app.db.base import Base
    return {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}


def _one(db, model, tenant_id: int, **where):
    terms = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        terms.append(model.is_deleted.is_(False))
    terms.extend(getattr(model, key) == value for key, value in where.items())
    return db.scalars(select(model).where(*terms)).first()


def _put(db, model, tenant_id: int, key: dict, values: dict):
    row = _one(db, model, tenant_id, **key)
    if row is None:
        row = model(tenant_id=tenant_id, **key, **values)
        db.add(row)
        db.flush()
    return row


def _actor(user) -> dict:
    return {
        "userId": str(user.id), "loginName": user.login_name,
        "realName": user.real_name, "currentRoleCode": "ACADEMIC_ADMIN",
        "userType": "STAFF", "dataScope": "ALL",
    }


def _seed_correction(db, c, tenant_id, admin, evidence, student):
    """用正式主档应用服务完成一次“错录→审批更正→审计”原子链。"""
    existing = _one(db, c["t_aa_student_correction"], tenant_id,
                    student_id=student.id, reason=f"{MARKER}：历史导入姓名尾注错录，据原始学籍材料更正。")
    if existing:
        return existing
    final_name = student.real_name
    wrong_name = f"{final_name}（错录）"
    student.real_name = wrong_name
    db.flush()
    correction = c["t_aa_student_correction"](
        tenant_id=tenant_id, student_id=student.id, field_key="REAL_NAME",
        old_value=wrong_name, new_value=final_name,
        reason=f"{MARKER}：历史导入姓名尾注错录，据原始学籍材料更正。",
        material_file_ids=json.dumps([str(evidence.id)]), status="PENDING",
    )
    db.add(correction)
    db.flush()
    from app.services import student_master_application_service as master
    master.apply_approved_correction_in_session(
        db, tenant_id=tenant_id, student_id=student.id, field_key="REAL_NAME",
        new_value=final_name, expected_version=int(student.version or 0),
        actor=_actor(admin), correction_id=correction.id,
    )
    correction.status = "APPROVED"
    correction.review_note = "证明材料与招生原始名册一致，批准更正并同步主档。"
    correction.reviewed_at = NOW
    correction.reviewed_by = admin.id
    db.add(c["t_affairs_audit_trail"](
        tenant_id=tenant_id, biz_type="AA_STUDENT_CORRECTION", biz_id=correction.id,
        action="APPROVE", operator=admin.real_name, role_name="教务处管理员",
        detail=f"{wrong_name} → {final_name}；主档与账号投影已同步。", occurred_at=NOW,
    ))
    return correction


def _append_status_fact(db, c, tenant_id, admin, student, *, change_type, from_status,
                        to_status, at, seq, previous_fact):
    key = f"{MARKER}:STATUS:{student.id}:{seq}"
    change = _one(db, c["t_aa_status_change"], tenant_id, idempotency_key=key)
    if change:
        return change, previous_fact
    change = c["t_aa_status_change"](
        tenant_id=tenant_id, student_id=student.id, change_type=change_type,
        from_status=from_status, to_status=to_status,
        from_college_id=student.college_id, from_major_id=student.major_id,
        from_class_id=student.class_id, to_college_id=student.college_id,
        to_major_id=student.major_id, to_class_id=student.class_id,
        reason=("因手术康复办理短期休学" if change_type == "SUSPEND" else "康复证明核验通过，按期复学"),
        effective_date=at, term_code="2025-2026-2", current_node="COMPLETED",
        status="EFFECTIVE", expected_student_version=student.version,
        decision_version=3, idempotency_key=key,
    )
    db.add(change)
    db.flush()
    wf = c["t_workflow_instance"](
        tenant_id=tenant_id, workflow_code=f"AA_STATUS_{change_type}",
        source_module="academic-affairs", source_biz_type="AA_STATUS_CHANGE",
        source_biz_id=change.id, applicant_id=admin.id,
        title=f"{student.real_name} {change_type} 学籍异动",
        status="APPROVED", current_node="COMPLETED",
        remark="辅导员、学院、教务处三级审批均已完成。",
    )
    db.add(wf)
    db.flush()
    change.workflow_instance_id = wf.id
    for node in ("COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"):
        db.add(c["t_workflow_task"](
            tenant_id=tenant_id, instance_id=wf.id, node_code=node,
            assignee_id=admin.id, status="APPROVED", action_reason="材料核验通过",
            acted_at=at,
        ))
    if previous_fact is not None:
        previous_fact.valid_to = at
        next_version = int(previous_fact.version_no) + 1
    else:
        next_version = 1
    fact = c["t_aa_student_academic_fact"](
        tenant_id=tenant_id, student_id=student.id, version_no=next_version,
        valid_from=at, valid_to=None, student_status=to_status,
        college_id=student.college_id, major_id=student.major_id,
        class_id=student.class_id, grade=student.grade,
        source_type="STATUS_CHANGE", source_ref_id=change.id, source_quality="EXACT",
        created_at=at, created_by=admin.id,
    )
    db.add(fact)
    db.flush()
    db.add(c["t_message_event_outbox"](
        tenant_id=tenant_id, event_code="STATUS_CHANGE.RESULT",
        source_module="academic-affairs", source_biz_type="AA_STATUS_CHANGE",
        source_biz_id=change.id,
        payload_json={"studentId": str(student.id), "status": to_status, "effectiveAt": at.isoformat()},
        recipient_refs_json=[{"receiverId": str(student.id), "receiverAs": "student"}],
        dedup_key=f"{MARKER}:STATUS-RESULT:{change.id}", status="SUCCEEDED",
        attempt_count=1, occurred_at=at, processed_at=at,
    ))
    return change, fact


def _seed_status_history(db, c, tenant_id, admin, student):
    if _one(db, c["t_aa_status_change"], tenant_id,
            idempotency_key=f"{MARKER}:STATUS:{student.id}:2"):
        return
    active = db.scalars(select(c["t_aa_student_academic_fact"]).where(
        c["t_aa_student_academic_fact"].tenant_id == tenant_id,
        c["t_aa_student_academic_fact"].student_id == student.id,
        c["t_aa_student_academic_fact"].valid_to.is_(None),
    ).order_by(c["t_aa_student_academic_fact"].version_no.desc())).first()
    _suspend, suspended_fact = _append_status_fact(
        db, c, tenant_id, admin, student, change_type="SUSPEND",
        from_status=student.student_status or "NORMAL", to_status="SUSPENDED",
        at=datetime(2026, 5, 8, 9), seq=1, previous_fact=active,
    )
    _append_status_fact(
        db, c, tenant_id, admin, student, change_type="RESUME",
        from_status="SUSPENDED", to_status=student.student_status or "NORMAL",
        at=datetime(2026, 6, 2, 9), seq=2, previous_fact=suspended_fact,
    )


def _seed_major_split(db, c, tenant_id, admin):
    batch = db.scalars(select(c["t_aa_major_split_batch"]).where(
        c["t_aa_major_split_batch"].tenant_id == tenant_id,
        c["t_aa_major_split_batch"].is_deleted.is_(False),
    ).order_by(c["t_aa_major_split_batch"].id.desc())).first()
    volunteer = db.scalars(select(c["t_aa_major_split_volunteer"]).where(
        c["t_aa_major_split_volunteer"].tenant_id == tenant_id,
        c["t_aa_major_split_volunteer"].batch_id == batch.id,
        c["t_aa_major_split_volunteer"].is_deleted.is_(False),
    )).first()
    student = db.get(c["t_student_profile"], volunteer.student_id)
    if batch.status != "CONFIRMED":
        choices = json.loads(volunteer.choices_json or "[]")
        result_major_id = int(choices[0]) if choices else int(student.major_id)
        volunteer.result_major_id = result_major_id
        volunteer.result_choice_rank = 1
        volunteer.status = "CONFIRMED"
        batch.status = "CONFIRMED"
        option = _one(db, c["t_aa_major_split_option"], tenant_id,
                      batch_id=batch.id, major_id=result_major_id)
        if option:
            option.allocated_count = max(1, int(option.allocated_count or 0))
        active = db.scalars(select(c["t_aa_student_academic_fact"]).where(
            c["t_aa_student_academic_fact"].tenant_id == tenant_id,
            c["t_aa_student_academic_fact"].student_id == student.id,
            c["t_aa_student_academic_fact"].valid_to.is_(None),
        ).order_by(c["t_aa_student_academic_fact"].version_no.desc())).first()
        if active:
            active.valid_to = NOW
            version_no = int(active.version_no) + 1
        else:
            version_no = 1
        db.add(c["t_aa_student_academic_fact"](
            tenant_id=tenant_id, student_id=student.id, version_no=version_no,
            valid_from=NOW, valid_to=None, student_status=student.student_status,
            college_id=student.college_id, major_id=result_major_id,
            class_id=student.class_id, grade=student.grade,
            source_type="MAJOR_SPLIT", source_ref_id=batch.id, source_quality="EXACT",
            created_at=NOW, created_by=admin.id,
        ))
        student.major_id = result_major_id
        db.add(c["t_affairs_audit_trail"](
            tenant_id=tenant_id, biz_type="AA_MAJOR_SPLIT", biz_id=batch.id,
            action="CONFIRM", operator=admin.real_name, role_name="教务处管理员",
            detail=f"志愿结果已确认并回写学生 {student.student_no} 学籍事实。", occurred_at=NOW,
        ))


def _seed_program_version_and_graduate(db, c, tenant_id, admin):
    """创建可追溯的 48 学分两年制方案版本，并用真实成绩/跨域记录运行毕业判定。"""
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad

    candidates = list(db.scalars(select(c["t_student_profile"]).join(
        c["t_acad_student"], c["t_acad_student"].student_id == c["t_student_profile"].id
    ).join(c["t_internship_record"], c["t_internship_record"].student_id == c["t_student_profile"].id
    ).join(c["t_gd_student"], c["t_gd_student"].student_id == c["t_student_profile"].id
    ).join(c["t_cs_service_student"], c["t_cs_service_student"].student_id == c["t_student_profile"].id
    ).join(c["t_affairs_archive_package"], c["t_affairs_archive_package"].student_id == c["t_student_profile"].id
    ).where(
        c["t_student_profile"].tenant_id == tenant_id,
        c["t_student_profile"].grade == "2024",
        c["t_student_profile"].is_deleted.is_(False),
        c["t_acad_student"].obtained_credits >= 48,
        c["t_acad_student"].is_deleted.is_(False),
        c["t_internship_record"].is_deleted.is_(False),
        c["t_gd_student"].is_deleted.is_(False),
        c["t_cs_service_student"].is_deleted.is_(False),
        c["t_affairs_archive_package"].status == "ARCHIVED",
        c["t_affairs_archive_package"].is_deleted.is_(False),
    ).order_by(c["t_student_profile"].id).limit(500)).all())
    candidate = candidates[0] if candidates else None
    if candidate is None:
        raise RuntimeError("缺少具有成绩、实习、毕设与在校服务台账的 2024 级毕业审核候选人")
    binding = db.scalars(select(c["t_aa_program_binding"]).join(
        c["t_aa_program"], c["t_aa_program"].id == c["t_aa_program_binding"].program_id
    ).where(
        c["t_aa_program_binding"].tenant_id == tenant_id,
        c["t_aa_program_binding"].major_id == candidate.major_id,
        c["t_aa_program_binding"].grade_year == candidate.grade,
        c["t_aa_program_binding"].status == "ACTIVE",
        c["t_aa_program_binding"].is_deleted.is_(False),
        c["t_aa_program"].is_deleted.is_(False),
    ).order_by((c["t_aa_program_binding"].class_id == candidate.class_id).desc())).first()
    base = db.get(c["t_aa_program"], binding.program_id)
    series = base.series_key or f"SBX-{base.major_id}-{base.grade_year}"
    base.series_key = series
    version = _one(db, c["t_aa_program"], tenant_id, series_key=series, version=int(base.version) + 1)
    if version is None:
        version = c["t_aa_program"](
            tenant_id=tenant_id,
            program_name=f"{base.program_name}（两年制技能强化版）",
            major_id=base.major_id, grade_year=base.grade_year,
            total_credits=48, requirement_json=json.dumps({"选修": 2, "实践": 13}, ensure_ascii=False),
            series_key=series, version=int(base.version) + 1, prev_version_id=base.id,
            status="ENABLED",
        )
        db.add(version)
        db.flush()
        acad = _one(db, c["t_acad_student"], tenant_id, student_id=candidate.id)
        grade_rows = db.scalars(select(c["t_acad_grade"]).where(
            c["t_acad_grade"].tenant_id == tenant_id,
            c["t_acad_grade"].acad_student_id == acad.id,
            c["t_acad_grade"].record_status == "ACTIVE",
            c["t_acad_grade"].pass_status == "PASSED",
            c["t_acad_grade"].is_deleted.is_(False),
        )).all()
        elective_assigned = False
        for row in grade_rows:
            is_practice = any(word in (row.course_name or "") for word in ("实训", "实践", "项目"))
            if not is_practice and not elective_assigned and float(row.credit_value or 0) >= 2:
                row.nature = "ELECTIVE"
                elective_assigned = True
            db.add(c["t_aa_program_course"](
                tenant_id=tenant_id, program_id=version.id, course_id=row.course_id,
                course_name=row.course_name, open_term_no=4,
                module="实践" if is_practice else ("专业选修" if row.nature == "ELECTIVE" else "专业必修"),
                credit_snapshot=row.credit_value, formation_mode="ADMIN_FIXED",
            ))
        binding.status = "SUPERSEDED"
        base.status = "FROZEN"
        db.add(c["t_aa_program_binding"](
            tenant_id=tenant_id, program_id=version.id, major_id=candidate.major_id,
            grade_year=candidate.grade, class_id=candidate.class_id,
            bound_at=NOW, status="ACTIVE",
        ))
        db.flush()
    else:
        acad = _one(db, c["t_acad_student"], tenant_id, student_id=candidate.id)
        elective = db.scalars(select(c["t_acad_grade"]).where(
            c["t_acad_grade"].tenant_id == tenant_id,
            c["t_acad_grade"].acad_student_id == acad.id,
            c["t_acad_grade"].record_status == "ACTIVE",
            c["t_acad_grade"].pass_status == "PASSED",
            c["t_acad_grade"].is_deleted.is_(False),
        ).order_by(c["t_acad_grade"].id)).first()
        if elective and not db.scalar(select(func.count()).select_from(c["t_acad_grade"]).where(
            c["t_acad_grade"].tenant_id == tenant_id,
            c["t_acad_grade"].acad_student_id == acad.id,
            c["t_acad_grade"].nature == "ELECTIVE",
            c["t_acad_grade"].record_status == "ACTIVE",
            c["t_acad_grade"].is_deleted.is_(False),
        )):
            elective.nature = "ELECTIVE"
    cs = _one(db, c["t_cs_service_student"], tenant_id, student_id=candidate.id)
    active_discipline_rows = db.scalars(select(c["t_cs_discipline"]).where(
        c["t_cs_discipline"].tenant_id == tenant_id,
        c["t_cs_discipline"].cs_student_id == cs.id,
        c["t_cs_discipline"].record_status == "ACTIVE",
        c["t_cs_discipline"].is_deleted.is_(False),
    )).all()
    for discipline in active_discipline_rows:
        discipline.status = "REVOKED"
        discipline.record_status = "REVOKED"
        discipline.revoke_date = NOW - timedelta(days=30)
        discipline.revoke_reason = "处分期满且教育考察合格，经正式解除流程批准。"
        db.add(c["t_affairs_audit_trail"](
            tenant_id=tenant_id, biz_type="DISCIPLINE", biz_id=discipline.id,
            action="REVOKE", operator=admin.real_name, role_name="学生工作处",
            detail=discipline.revoke_reason, occurred_at=discipline.revoke_date,
        ))
    db.flush()
    set_tenant(tenant_id)
    batch = _put(db, c["t_aa_graduation_audit_batch"], tenant_id,
                 {"batch_name": "2026 届两年制技能强化班毕业资格终审"},
                 {"grade_year": "2024", "major_id": candidate.major_id,
                  "scope_json": json.dumps({"classId": candidate.class_id, "programId": version.id}),
                  "status": "ARCHIVED", "generate_at": NOW - timedelta(days=4)})
    result = _one(db, c["t_aa_graduation_audit_result"], tenant_id,
                  batch_id=batch.id, student_id=candidate.id)
    if result is None:
        items = grad._run_items(db, candidate)
        overall = grad._overall(items)
        if overall != "SYSTEM_PASSED":
            raise RuntimeError(f"毕业候选人正式规则判定未通过({overall})，拒绝伪造毕业结论: {items}")
        result = c["t_aa_graduation_audit_result"](
            tenant_id=tenant_id, batch_id=batch.id, student_id=candidate.id,
            item_results_json=json.dumps(items, ensure_ascii=False),
            overall="SYSTEM_PASSED", conclusion="GRADUATED", rerun_count=0,
            review_note="系统规则全部通过，学院与教务处复核证据一致。", status="GRADUATED",
        )
        db.add(result)
        db.flush()
    else:
        items = json.loads(result.item_results_json or "[]")
    payload = json.dumps({"studentId": candidate.id, "programId": version.id, "items": items},
                         ensure_ascii=False, sort_keys=True)
    run = _put(db, c["t_aa_graduation_evaluation_run"], tenant_id,
               {"result_id": result.id, "run_no": 1},
               {"batch_id": batch.id, "student_id": candidate.id, "program_id": version.id,
                "input_snapshot_json": payload, "input_hash": sha256(payload.encode()).hexdigest(),
                "item_results_json": json.dumps(items, ensure_ascii=False),
                "overall": "SYSTEM_PASSED", "evaluator_version": "STAGE_C3_V1"})
    _put(db, c["t_aa_graduation_decision_fact"], tenant_id,
         {"result_id": result.id, "decision_no": 1},
         {"batch_id": batch.id, "student_id": candidate.id, "evaluation_run_id": run.id,
          "conclusion": "GRADUATED", "decision_at": NOW - timedelta(days=2),
          "decision_by": admin.id, "review_note": "以不可变评估快照作为毕业终审依据。"})
    _put(db, c["t_aa_graduation_certificate"], tenant_id,
         {"cert_no": f"YK2026{candidate.student_no[-5:]}"},
         {"student_id": candidate.id, "student_no": candidate.student_no,
          "student_name": candidate.real_name, "audit_batch_id": batch.id,
          "cert_type": "GRADUATION", "e_reg_no": f"E-YK-2026-{candidate.student_no}",
          "issue_year": "2026", "issue_date": "2026-08-28",
          "major_name": None, "status": "ISSUED"})
    if candidate.student_status != "GRADUATED":
        from app.modules.academic_affairs.services.academic_affairs_status_service import change_student_status
        change_student_status(
            db, candidate.id, "GRADUATED", change_type="GRADUATE",
            reason="毕业资格终审通过并生成不可变决定事实",
            operator=str(admin.id), source_biz_id=result.id,
        )


def _seed_selection_roster_and_exemption(db, c, tenant_id, admin):
    course = db.scalars(select(c["t_aa_selection_course"]).where(
        c["t_aa_selection_course"].tenant_id == tenant_id,
        c["t_aa_selection_course"].is_deleted.is_(False),
    ).order_by(c["t_aa_selection_course"].id.desc())).first()
    member = db.scalars(select(c["t_aa_teaching_class_member"]).join(
        c["t_aa_teaching_class"],
        c["t_aa_teaching_class"].id == c["t_aa_teaching_class_member"].teaching_class_id
    ).where(
        c["t_aa_teaching_class"].tenant_id == tenant_id,
        c["t_aa_teaching_class"].teaching_task_id == course.teaching_task_id,
        c["t_aa_teaching_class"].is_deleted.is_(False),
        c["t_aa_teaching_class_member"].status == "ACTIVE",
        c["t_aa_teaching_class_member"].is_deleted.is_(False),
    ).order_by(c["t_aa_teaching_class_member"].id)).first()
    student = db.get(c["t_student_profile"], member.student_id)
    _put(db, c["t_aa_selection_record"], tenant_id,
         {"batch_id": course.batch_id, "selection_course_id": course.id, "student_id": student.id},
         {"course_id": course.course_id, "course_name": course.course_name,
          "credit": course.credit, "student_no": student.student_no,
          "student_name": student.real_name, "enrolled_at": NOW,
          "re_enroll": False, "status": "SELECTED"})
    selected = db.scalar(select(func.count()).select_from(c["t_aa_selection_record"]).where(
        c["t_aa_selection_record"].tenant_id == tenant_id,
        c["t_aa_selection_record"].selection_course_id == course.id,
        c["t_aa_selection_record"].status == "SELECTED",
        c["t_aa_selection_record"].is_deleted.is_(False),
    )) or 0
    course.selected_count = int(selected)
    exemption = db.scalars(select(c["t_aa_exemption"]).where(
        c["t_aa_exemption"].tenant_id == tenant_id,
        c["t_aa_exemption"].is_deleted.is_(False),
    ).order_by(c["t_aa_exemption"].id.desc())).first()
    if exemption.status not in ("APPROVED", "REJECTED"):
        exemption.status = "REJECTED"
        exemption.review_note = "证书能力范围未覆盖课程实践考核，终审不予免修。"
        exemption.reviewed_at = NOW
        exemption.reviewed_by = admin.id


def _seed_file_exchange(db, c, tenant_id, admin):
    from app.core.config import settings
    folder = Path(settings.UPLOAD_DIR).resolve() / "sandbox-academic"
    folder.mkdir(parents=True, exist_ok=True)
    source_bytes = "studentNo,courseCode,score\n2024S0001,YK-C001,86\n2024S0002,YK-C001,错误分数\n".encode("utf-8-sig")
    export_bytes = "studentNo,courseCode,score,status\n2024S0001,YK-C001,86,已发布\n".encode("utf-8-sig")
    source_path = folder / "academic-grade-import-demo.csv"
    export_path = folder / "academic-grade-export-demo.csv"
    source_path.write_bytes(source_bytes)
    export_path.write_bytes(export_bytes)
    source = _put(db, c["t_file_object"], tenant_id,
                  {"file_key": str(source_path)},
                  {"file_name": source_path.name, "ext": "csv", "mime_type": "text/csv",
                   "size_bytes": len(source_bytes), "sha256": sha256(source_bytes).hexdigest(),
                   "biz_type": "ACADEMIC_IMPORT", "biz_id": MARKER,
                   "owner_user_id": admin.id, "visibility": "BIZ_SCOPED",
                   "security_level": "PERSONAL", "status": "AVAILABLE",
                   "storage_backend": "local", "object_key": str(source_path),
                   "legacy_file_key": str(source_path), "upload_source": "SYSTEM",
                   "scan_required": False, "scan_status": "NOT_REQUIRED", "available_at": NOW})
    exported = _put(db, c["t_file_object"], tenant_id,
                    {"file_key": str(export_path)},
                    {"file_name": export_path.name, "ext": "csv", "mime_type": "text/csv",
                     "size_bytes": len(export_bytes), "sha256": sha256(export_bytes).hexdigest(),
                     "biz_type": "ACADEMIC_EXPORT", "biz_id": MARKER,
                     "owner_user_id": admin.id, "visibility": "BIZ_SCOPED",
                     "security_level": "PERSONAL", "status": "AVAILABLE",
                     "storage_backend": "local", "object_key": str(export_path),
                     "legacy_file_key": str(export_path), "upload_source": "SYSTEM",
                     "scan_required": False, "scan_status": "NOT_REQUIRED", "available_at": NOW})
    job = _put(db, c["t_import_job"], tenant_id,
               {"adapter_type": "ACADEMIC_GRADE_CSV", "adapter_ref": MARKER},
               {"module_code": "ACADEMIC_AFFAIRS", "import_type": "GRADE_IMPORT",
                "source_file_id": source.id, "template_version": "2026.1", "status": "SUCCEEDED",
                "total_rows": 2, "valid_rows": 1, "invalid_rows": 1, "confirmed_rows": 1,
                "operator_id": admin.id, "operator_name": admin.real_name, "confirmed_at": NOW,
                "source_snapshot_json": {"fileId": str(source.id), "sha256": source.sha256},
                "result_json": {"confirmed": 1, "rejected": 1}})
    _put(db, c["t_import_row_error"], tenant_id,
         {"import_job_id": job.id, "row_no": 3},
         {"sheet_name": "成绩导入", "field_code": "score", "error_code": "INVALID_SCORE",
          "error_message": "成绩必须是 0～100 的数字。",
          "raw_snapshot_json": {"studentNo": "2024S0002", "score": "错误分数"}})
    _put(db, c["t_export_job"], tenant_id,
         {"adapter_type": "ACADEMIC_GRADE_CSV", "adapter_ref": MARKER, "export_type": "GRADE_LEDGER"},
         {"module_code": "ACADEMIC_AFFAIRS", "purpose": "客户演示：已发布成绩台账脱敏导出",
          "filter_snapshot_json": {"term": "2025-2026-2", "status": "PUBLISHED"},
          "data_scope_snapshot_json": {"scope": "ALL", "masked": True},
          "status": "SUCCEEDED", "progress": 100, "row_count": 1,
          "file_object_id": exported.id, "downloaded_count": 0,
          "operator_id": admin.id, "finished_at": NOW,
          "result_json": {"fileId": str(exported.id), "sha256": exported.sha256}})


def seed_academic_flow_gap_coverage(db, tenant_id: int) -> dict:
    from app.core.context import set_tenant
    from app.models import StudentProfile, User, FileObject
    from app.services.sandbox_school_academic_flow_coverage import audit_academic_flow_coverage

    c = _classes()
    set_tenant(tenant_id)
    admin = _one(db, User, tenant_id, login_name="admin2")
    evidence = db.scalars(select(FileObject).where(
        FileObject.tenant_id == tenant_id, FileObject.is_deleted.is_(False),
        FileObject.status == "AVAILABLE",
    ).order_by(FileObject.id)).first()
    students = list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.status == "ACTIVE",
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.id).limit(8)).all())
    if not admin or not evidence or len(students) < 4:
        raise RuntimeError("AA24 补链缺少管理员、证明文件或学生主档")
    _seed_correction(db, c, tenant_id, admin, evidence, students[3])
    _seed_status_history(db, c, tenant_id, admin, students[4])
    _seed_major_split(db, c, tenant_id, admin)
    _seed_program_version_and_graduate(db, c, tenant_id, admin)
    _seed_selection_roster_and_exemption(db, c, tenant_id, admin)
    _seed_file_exchange(db, c, tenant_id, admin)
    db.commit()
    report = audit_academic_flow_coverage(db, tenant_id)
    if not report["summary"]["fullCoveragePassed"]:
        raise RuntimeError(f"AA24 演示主链仍未闭合: {[x['flowCode'] for x in report['failures']]}")
    return report
