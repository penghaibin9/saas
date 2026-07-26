"""岗位实习 · 归档中心（P3-A）。按学生/批次/企业聚合 + 材料完整性检查 + 缺失提醒 + 归档动作。

材料清单（7 项）：三方协议(生效)、打卡记录、周报、企业评价(通过)、学生自评(已提交)、实习成绩(已发布)、指导记录。
归档包 package_file_id 预留（zip 打包能力接文件中心后启用，当前 partial，不伪造上传成功）。
owner + 数据范围复用 internship_service。审计 target_type=ARCHIVE。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAgreement, InternshipArchive, InternshipAuditTrail,
                        InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
                        InternshipGuidance, InternshipRecord, InternshipStudentEval,
                        RiskRecord, StudentProfile, WeeklyReport)
from app.modules.internship.services.internship_version import extract_expected_version, versioned_update
from app.services.db_service import _as_id, _iso, _tid, session

MATERIALS = [
    ("agreement", "三方协议"), ("checkin", "打卡记录"), ("weekly", "周报"),
    ("enterpriseEval", "企业评价"), ("studentEval", "学生自评"), ("score", "实习成绩"),
    ("guidance", "指导记录"),
]


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, aid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=aid, target_type="ARCHIVE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _exists(db, model, rec_id, *conds):
    return (db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == _tid(), model.is_deleted.is_(False),
        model.internship_id == rec_id, *conds)) or 0) > 0


def _materials(db, rec_id) -> dict:
    return {
        "agreement": _exists(db, InternshipAgreement, rec_id,
                             InternshipAgreement.status.in_(["EFFECTIVE", "ARCHIVED"])),
        "checkin": _exists(db, InternshipCheckin, rec_id),
        "weekly": _exists(db, WeeklyReport, rec_id),
        "enterpriseEval": _exists(db, InternshipEnterpriseEval, rec_id,
                                  InternshipEnterpriseEval.school_review_status == "APPROVED"),
        "studentEval": _exists(db, InternshipStudentEval, rec_id,
                               InternshipStudentEval.submit_status == "SUBMITTED"),
        "score": _exists(db, InternshipFinalScore, rec_id, InternshipFinalScore.status == "PUBLISHED"),
        "guidance": _exists(db, InternshipGuidance, rec_id, InternshipGuidance.status == "NORMAL"),
    }


def _completeness(materials) -> tuple[int, list[str]]:
    present = sum(1 for key, _label in MATERIALS if materials.get(key))
    missing = [label for key, label in MATERIALS if not materials.get(key)]
    pct = round(present / len(MATERIALS) * 100)
    return pct, missing


def _archive_row(db, rec_id):
    return db.scalars(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(), InternshipArchive.internship_id == rec_id,
        InternshipArchive.is_deleted.is_(False))).first()


def _row(db, r, stu):
    mats = _materials(db, r.id)
    pct, missing = _completeness(mats)
    arch = _archive_row(db, r.id)
    return {
        "id": str(r.id), "studentName": stu.real_name if stu else "-",
        "studentNo": stu.student_no if stu else "-", "advisorName": r.advisor_name or "",
        "enterpriseName": r.enterprise_name or "", "recordStatus": r.status,
        "completeness": pct, "missing": missing, "materials": mats,
        "archived": bool(arch and arch.status == "ARCHIVED"),
        "archivedAt": _iso(arch.archived_at) if arch else "",
        "packageReady": bool(arch and arch.package_file_id),
        "version": int(arch.version or 0) if arch else None,
        "recordVersion": int(r.version or 0),
    }


def _scoped_records(db, user, batch_id=None, enterprise=None):
    scope, in_scope = _scope_ctx(user)
    scoped = scope.get("mode") == "SCOPED"
    recs = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False))).all()
    out = []
    for r in recs:
        stu = db.get(StudentProfile, r.student_id)
        if scoped and not in_scope(scope, db, r, stu):
            continue
        if batch_id and str(r.batch_id) != str(batch_id):
            continue
        if enterprise and (r.enterprise_name or "") != enterprise:
            continue
        out.append((r, stu))
    return out


def list_by_student(page, page_size, keyword=None, batch_id=None, only_incomplete=False, user=None):
    with session() as db:
        from app.modules.internship.services.internship_batch_context import resolve_batch
        batch = resolve_batch(db, batch_id)
        pairs = _scoped_records(db, user, batch_id=batch.id)
        items = []
        for r, stu in pairs:
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            row = _row(db, r, stu)
            if only_incomplete and row["completeness"] >= 100:
                continue
            items.append(row)
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_archive(internship_id, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        r = db.get(InternshipRecord, _as_id(internship_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, r.student_id)
        if not in_scope(scope, db, r, stu):
            raise no_permission("该学生不在你的数据范围内")
        row = _row(db, r, stu)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "ARCHIVE",
            InternshipAuditTrail.target_id == r.id).order_by(InternshipAuditTrail.id)).all()
        row["auditTrail"] = [{"action": t.action, "operator": t.operator_name or "",
                              "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                             for t in trail]
        row["materialLabels"] = [{"key": k, "label": lb, "present": row["materials"].get(k)}
                                 for k, lb in MATERIALS]
        return row


def archive_student(user, internship_id, force=False, expected_version=None,
                    force_reason="", evidence_file_ids=None,
                    record_expected_version=None) -> dict:
    """归档：快照材料完整性并锁定。默认要求 100% 完整；force=True 允许带缺失归档（记 missing）。"""
    scope, in_scope = _scope_ctx(user)
    if force:
        import re
        from app.core.permissions import enforce_permission, is_super_admin
        enforce_permission(user or {}, "internship.archive.force")
        role = ((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()
        if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
            raise no_permission("仅学校管理员可执行强制归档")
        if len(re.findall(r"[\u4e00-\u9fff]", (force_reason or "").strip())) < 10:
            raise AppException("VALIDATION_ERROR", "强制归档原因必填且不少于 10 个汉字")
        if not evidence_file_ids:
            raise AppException("VALIDATION_ERROR", "强制归档必须提供依据文件")
    with session() as db:
        r = db.get(InternshipRecord, _as_id(internship_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, r.student_id)
        if not in_scope(scope, db, r, stu):
            raise no_permission("只能归档本人数据范围内的学生")
        mats = _materials(db, r.id)
        pct, missing = _completeness(mats)
        if pct < 100 and not force:
            raise AppException("DATA_CONFLICT", f"材料不完整（缺：{'、'.join(missing)}），"
                               f"如需带缺失归档请确认强制归档")
        # P0-11：开放高风险 / 待批周报阻断普通归档
        open_high = db.scalar(select(func.count()).select_from(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == r.id,
            RiskRecord.is_deleted.is_(False), RiskRecord.risk_level == "HIGH",
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")))) or 0
        if open_high and not force:
            raise AppException("DATA_CONFLICT", "存在未关闭的高风险，请先处置后再归档（或强制归档）")
        pending_wr = db.scalar(select(func.count()).select_from(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id == r.id,
            WeeklyReport.is_deleted.is_(False), WeeklyReport.status == "PENDING_REVIEW")) or 0
        if pending_wr and not force:
            raise AppException("DATA_CONFLICT", "存在待批周报，请先批阅后再归档（或强制归档）")
        bypassed = []
        if pct < 100:
            bypassed.extend([f"材料缺失:{item}" for item in missing])
        if open_high:
            bypassed.append(f"未关闭高风险:{int(open_high)}")
        if pending_wr:
            bypassed.append(f"待批周报:{int(pending_wr)}")
        from app.modules.internship.services.internship_compliance_rules import rule_version_label
        batch = db.get(InternshipBatch, r.batch_id) if r.batch_id else None
        force_meta = {
            "force_bypassed_items": bypassed if force else None,
            "force_rule_version": rule_version_label(batch) if force else None,
            "force_approved_role": ((user or {}).get("currentRoleCode") or "") if force else None,
            "force_approved_by": _op_name(user) if force else None,
        }
        arch = _archive_row(db, r.id)
        new = arch is None
        previous_status = r.status
        if new:
            record_ver = extract_expected_version({"expectedVersion": expected_version})
            new_record_ver = versioned_update(
                db, InternshipRecord, entity_id=r.id, tenant_id=_tid(), expected_version=record_ver,
                expected_status=r.status, values={"status": "ARCHIVED"})
            arch = InternshipArchive(
                tenant_id=_tid(), internship_id=r.id, student_id=r.student_id,
                batch_id=r.batch_id, previous_record_status=previous_status)
            db.add(arch)
            arch.completeness = pct
            arch.missing_items = "、".join(missing) or None
            arch.material_snapshot = mats
            arch.status = "ARCHIVED"
            arch.archived_by_name = _op_name(user)
            arch.archived_at = datetime.utcnow()
            arch.force_reason = (force_reason or "").strip() or None
            arch.force_evidence_file_ids = evidence_file_ids or None
            for key, value in force_meta.items():
                setattr(arch, key, value)
            arch.version = (arch.version or 0) + 1
            archive_ver = arch.version
        else:
            record_ver = extract_expected_version(
                {"expectedVersion": record_expected_version})
            new_record_ver = versioned_update(
                db, InternshipRecord, entity_id=r.id, tenant_id=_tid(),
                expected_version=record_ver, expected_status=r.status,
                values={"status": "ARCHIVED"})
            archive_ver = versioned_update(
                db, InternshipArchive, entity_id=arch.id, tenant_id=_tid(),
                expected_version=extract_expected_version({"expectedVersion": expected_version}),
                expected_status=arch.status,
                values={"completeness": pct, "missing_items": "、".join(missing) or None,
                        "material_snapshot": mats, "status": "ARCHIVED",
                        "archived_by_name": _op_name(user), "archived_at": datetime.utcnow(),
                        "previous_record_status": previous_status,
                        "force_reason": (force_reason or "").strip() or None,
                        "force_evidence_file_ids": evidence_file_ids or None})
            for key, value in force_meta.items():
                setattr(arch, key, value)
        db.flush()
        _trail(db, r.id, "ARCHIVE", {"completeness": pct, "missing": missing, "force": force,
                                     "forceReason": (force_reason or "").strip(),
                                     "evidenceFileIds": evidence_file_ids or []},
               operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "completeness": pct, "missing": missing, "archived": True,
                "version": archive_ver, "recordVersion": new_record_ver}


def build_package(user, internship_id) -> dict:
    """生成归档 zip（manifest + 材料清单 + 已有扫描件），落文件中心并写 package_file_id。"""
    import io
    import json
    import zipfile

    from app.services import file_service

    scope, in_scope = _scope_ctx(user)
    with session() as db:
        r = db.get(InternshipRecord, _as_id(internship_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, r.student_id)
        if not in_scope(scope, db, r, stu):
            raise no_permission("该学生不在你的数据范围内")
        arch = _archive_row(db, r.id)
        if not arch or arch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅已归档学生可生成归档包")
        mats = _materials(db, r.id)
        pct, missing = _completeness(mats)
        manifest = {
            "studentName": stu.real_name if stu else "-",
            "studentNo": stu.student_no if stu else "-",
            "advisorName": r.advisor_name or "",
            "enterpriseName": r.enterprise_name or "",
            "positionName": r.position_name or "",
            "completeness": pct,
            "missing": missing,
            "materials": mats,
            "archivedAt": _iso(arch.archived_at),
            "archivedBy": arch.archived_by_name or "",
        }
        checklist = ["实习归档材料清单", "=" * 40]
        for key, label in MATERIALS:
            checklist.append(f"{'[√]' if mats.get(key) else '[×]'} {label}")
        if missing:
            checklist.append("")
            checklist.append("缺失项：" + "、".join(missing))
        checklist.append("")
        checklist.append("说明：本包为归档快照；各材料原件以系统 file_id 关联为准。")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("材料清单.txt", "\n".join(checklist))
            # 三方协议扫描件（如有）
            agr = db.scalars(select(InternshipAgreement).where(
                InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == r.id,
                InternshipAgreement.is_deleted.is_(False)).order_by(InternshipAgreement.id.desc())).first()
            if agr and agr.file_id:
                resolved = file_service.resolve_download(agr.file_id)
                if resolved:
                    path, fname = resolved
                    zf.write(path, f"attachments/{fname or '三方协议扫描件'}")
        zip_bytes = buf.getvalue()
        sname = (stu.real_name if stu else "学生").replace("/", "_")
        meta = file_service.store_bytes(zip_bytes, f"实习归档_{sname}.zip", biz_type="ARCHIVE_PACKAGE",
                                        mime_type="application/zip")
        arch.package_file_id = meta["fileId"]
        _trail(db, r.id, "PACKAGE", {"fileId": meta["fileId"], "fileName": meta["fileName"]},
               operator=_op_name(user))
        db.commit()
        return {"fileId": meta["fileId"], "fileName": meta["fileName"],
                "sizeBytes": meta["sizeBytes"], "packageReady": True}


def revoke_archive(user, internship_id, reason="", expected_version=None,
                   record_expected_version=None) -> dict:
    from app.core.permissions import is_super_admin
    role = ((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()
    if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
        raise no_permission("仅学校管理员可撤销归档")
    import re
    if len(re.findall(r"[\u4e00-\u9fff]", (reason or "").strip())) < 10:
        raise AppException("VALIDATION_ERROR", "撤销归档原因必填且不少于 10 个汉字")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        r = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(internship_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, r.student_id)
        if not in_scope(scope, db, r, stu):
            raise no_permission("只能撤销本人数据范围内的归档")
        arch = _archive_row(db, r.id)
        if not arch or arch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "该学生未归档")
        archive_ver = extract_expected_version({"expectedVersion": expected_version})
        record_ver = extract_expected_version({"expectedVersion": record_expected_version})
        if int(r.version or 0) != record_ver:
            raise AppException("DATA_CONFLICT", "实习学生记录已被其他用户修改，请刷新后重试")
        restore_status = arch.previous_record_status or "ASSESSING"
        if restore_status == "ARCHIVED":
            restore_status = "ASSESSING"
        new_ver = versioned_update(
            db, InternshipArchive, entity_id=arch.id, tenant_id=_tid(),
            expected_version=archive_ver, expected_status="ARCHIVED",
            values={"status": "REVOKED", "revoked_by_name": _op_name(user),
                    "revoked_at": datetime.utcnow(), "revoke_reason": reason.strip(),
                    "package_invalidated_at": datetime.utcnow() if arch.package_file_id else None})
        r.status = restore_status
        r.version = record_ver + 1
        _trail(db, r.id, "REVOKE", {"reason": reason.strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "archived": False, "version": new_ver,
                "recordVersion": r.version, "recordStatus": restore_status,
                "packageInvalidated": bool(arch.package_file_id)}


def _aggregate(pairs, db, group_key):
    groups = {}
    for r, stu in pairs:
        gk = group_key(r) or "未分组"
        g = groups.setdefault(gk, {"group": gk, "total": 0, "archived": 0, "complete": 0, "sum": 0})
        g["total"] += 1
        mats = _materials(db, r.id)
        pct, _ = _completeness(mats)
        g["sum"] += pct
        if pct >= 100:
            g["complete"] += 1
        arch = _archive_row(db, r.id)
        if arch and arch.status == "ARCHIVED":
            g["archived"] += 1
    out = []
    for g in groups.values():
        g["avgCompleteness"] = round(g["sum"] / g["total"]) if g["total"] else 0
        g["archiveRate"] = round(g["archived"] / g["total"] * 100, 1) if g["total"] else 0
        del g["sum"]
        out.append(g)
    return sorted(out, key=lambda x: x["group"])


def by_batch(user=None, batch_id=None):
    from app.models import InternshipBatch
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        pairs = _scoped_records(db, user, batch_id=batch.id)
        names = {b.id: b.batch_name for b in db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == _tid())).all()}
        return _aggregate(pairs, db, lambda r: names.get(r.batch_id, f"批次{r.batch_id}") if r.batch_id else "未分批")


def by_enterprise(user=None, batch_id=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        pairs = _scoped_records(db, user, batch_id=batch.id)
        return _aggregate(pairs, db, lambda r: r.enterprise_name or "未分配企业")


def export_archives(user=None, keyword=None, batch_id=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_by_student(1, 100000, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "指导教师", "企业", "完整度(%)", "缺失材料", "是否已归档", "归档时间"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["completeness"], "、".join(it["missing"]) or "无", "是" if it["archived"] else "否",
             it["archivedAt"] or "—"] for it in items]
    wm = f"岗位实习中心·归档台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("实习归档台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "实习归档台账.xlsx", len(items))
