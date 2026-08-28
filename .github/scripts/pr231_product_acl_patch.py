from pathlib import Path


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} matches, got {actual}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# 1) Explicit authoritative internship scope wins over ambiguous legacy biz_id fallback.
replace_exact(
    "app/services/file_access_resolvers.py",
    '''    if not linked_leaves:\n        student_ids.update(ambiguous_student_ids)\n        internship_ids.update(ambiguous_internship_ids)\n    return student_ids, internship_ids\n''',
    '''    if not linked_leaves and not student_ids and not internship_ids:\n        # Only legacy bindings without any authoritative subject/scope may interpret\n        # the historical INTERNSHIP biz_id ambiguously. Once a current binding\n        # carries student/internship scope, never union an unrelated numeric biz_id.\n        student_ids.update(ambiguous_student_ids)\n        internship_ids.update(ambiguous_internship_ids)\n    return student_ids, internship_ids\n''',
)

# 2) Internal internship staff/admins must still pass the canonical record data-scope guard.
replace_exact(
    "app/services/file_access_resolvers.py",
    '''def _internship_staff_scope_allows(db, file_obj, bindings: list[Any], user: dict) -> bool:\n    \"\"\"仅放行与文件目标学生存在真实指导关系的实习教师。\"\"\"\n    if db is None or str(user.get(\"userType\") or \"\").upper() != \"TEACHER\":\n        return False\n    student_ids, internship_ids = _collect_internship_scope(file_obj, bindings, db)\n    if not student_ids and not internship_ids:\n        return False\n    try:\n        from app.models import InternshipRecord\n\n        clauses = []\n        if student_ids:\n            clauses.append(InternshipRecord.student_id.in_(student_ids))\n        if internship_ids:\n            clauses.append(InternshipRecord.id.in_(internship_ids))\n        rows = db.scalars(select(InternshipRecord).where(\n            InternshipRecord.tenant_id == int(file_obj.tenant_id),\n            InternshipRecord.is_deleted.is_(False),\n            or_(*clauses),\n        )).all()\n        actor_user_id = stable_user_id(user)\n        if actor_user_id is None:\n            return False\n        return any(\n            row.advisor_user_id is not None\n            and int(row.advisor_user_id) == actor_user_id\n            for row in rows\n        )\n    except Exception:\n        return False\n''',
    '''def _internship_staff_scope_allows(db, file_obj, bindings: list[Any], user: dict) -> bool:\n    \"\"\"岗位实习内部人员必须命中绑定目标记录，并通过统一实习数据范围。\n\n    正式文件仍不能只凭 uploader/通用文件权限读取；这里只接受学校内部教职工/\n    管理身份，并把 binding 冻结的 student/internship scope 交给业务 Authority 复核。\n    \"\"\"\n    actor_type = str((user or {}).get(\"userType\") or \"\").upper()\n    if db is None or actor_type not in {\"TEACHER\", \"STAFF\", \"ADMIN\", \"SCHOOL_ADMIN\"}:\n        return False\n    student_ids, internship_ids = _collect_internship_scope(file_obj, bindings, db)\n    if not student_ids and not internship_ids:\n        return False\n    try:\n        from app.models import InternshipRecord\n        from app.modules.internship.services.internship_scope import assert_internship_record_scope\n\n        clauses = []\n        if student_ids:\n            clauses.append(InternshipRecord.student_id.in_(student_ids))\n        if internship_ids:\n            clauses.append(InternshipRecord.id.in_(internship_ids))\n        rows = db.scalars(select(InternshipRecord).where(\n            InternshipRecord.tenant_id == int(file_obj.tenant_id),\n            InternshipRecord.is_deleted.is_(False),\n            or_(*clauses),\n        )).all()\n        for row in rows:\n            try:\n                assert_internship_record_scope(db, row.id, user or {}, \"访问岗位实习业务文件\")\n                return True\n            except Exception:\n                continue\n        return False\n    except Exception:\n        return False\n''',
)

# 3) Special-filing evidence must be bound with authoritative record/student/batch scope.
replace_exact(
    "app/modules/internship/services/internship_special_filing_service.py",
    '''        db.add(row)\n        db.flush()\n        for fid in file_ids:\n            file_service.bind_file_biz(fid, \"INTERNSHIP\", str(row.id), user=user, db=db)\n        _audit(db, row, \"CREATE\", user, {\n''',
    '''        db.add(row)\n        db.flush()\n        from app.services.file_business_binding_service import bind_file_to_business\n\n        scope = {\n            \"internshipId\": str(rec.id),\n            \"studentId\": str(rec.student_id),\n            \"batchId\": str(rec.batch_id or \"\"),\n            \"businessType\": \"SPECIAL_FILING\",\n            \"businessId\": str(row.id),\n        }\n        legacy_targets = {str(rec.id), str(rec.student_id), str(row.id)}\n        for fid in file_ids:\n            bind_file_to_business(\n                db,\n                file_id=fid,\n                biz_type=\"INTERNSHIP\",\n                biz_id=str(row.id),\n                actor=user or {},\n                subject_type=\"STUDENT\",\n                subject_id=str(rec.student_id),\n                relation_type=\"SPECIAL_FILING_EVIDENCE\",\n                module_code=\"INTERNSHIP\",\n                student_id=rec.student_id,\n                batch_id=str(rec.batch_id or \"\") or None,\n                scope=scope,\n                legacy_target_values=legacy_targets,\n            )\n        _audit(db, row, \"CREATE\", user, {\n''',
)

# 4) Regression: school internal admin in canonical scope can read; enterprise identity cannot.
replace_exact(
    "tests/test_file_student_internship_acl.py",
    '''        assert strict_scoped_binding_resolver(\n            db,\n            file_obj,\n            [binding],\n            {\"userType\": \"STUDENT\", \"studentNo\": other.student_no},\n            \"meta\",\n        ) is False\n        db.rollback()\n''',
    '''        assert strict_scoped_binding_resolver(\n            db,\n            file_obj,\n            [binding],\n            {\"userType\": \"STUDENT\", \"studentNo\": other.student_no},\n            \"meta\",\n        ) is False\n        assert strict_scoped_binding_resolver(\n            db,\n            file_obj,\n            [binding],\n            {\n                \"userId\": \"99001\", \"userType\": \"ADMIN\",\n                \"currentRoleCode\": \"SCHOOL_ADMIN\", \"tenantId\": str(TID),\n            },\n            \"meta\",\n        ) is True\n        assert strict_scoped_binding_resolver(\n            db,\n            file_obj,\n            [binding],\n            {\n                \"userId\": \"ent-99001\", \"userType\": \"ENTERPRISE\",\n                \"currentRoleCode\": \"ENTERPRISE_ADMIN\", \"tenantId\": str(TID),\n            },\n            \"meta\",\n        ) is False\n        db.rollback()\n''',
)

print("PR231 product ACL and special-filing authoritative binding patch applied")
