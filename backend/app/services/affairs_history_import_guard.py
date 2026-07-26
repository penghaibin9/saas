"""学工历史迁移安全门。

批次存入 Redis，多 worker 共享；确认使用分布式锁；记录固定为历史终态，
补齐处分投影、宿舍床位、成长事件和审计。Redis 不可用时 fail-closed。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.redis_client import cache_delete, cache_get_json, cache_set_json, cache_set_json_if_absent
from app.db.session import get_sessionmaker

_INSTALLED = False
_TTL = 1800
_ALLOWED_TYPES = {"DIFFICULT", "FUNDING", "DISCIPLINE", "DORM", "ORG_CADRE", "LEAGUE"}
_ALLOWED_AID_LEVELS = {"GENERAL", "DIFFICULT", "SPECIAL"}
_ALLOWED_DISC_TYPES = {"WARNING", "SERIOUS_WARNING", "DEMERIT", "PROBATION", "EXPEL"}
_ALLOWED_LEAGUE_STAGES = {"APPLICANT", "ACTIVIST", "DEVELOPMENT_TARGET", "PROBATIONARY", "FULL_MEMBER"}


def _tenant_id() -> int:
    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if tenant_id <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝学工历史导入")
    return tenant_id


def _key(batch_no: str) -> str:
    return f"affairs-history-import:{_tenant_id()}:{batch_no}"


def _lock_key(batch_no: str) -> str:
    return f"affairs-history-import-lock:{_tenant_id()}:{batch_no}"


def _persist(batch_no: str, batch: dict) -> None:
    if not cache_set_json(_key(batch_no), batch, _TTL):
        raise AppException("IMPORT_STORE_UNAVAILABLE", "历史导入共享存储不可用，请确认Redis正常后重试", http_status=503)


def _load(batch_no: str) -> dict:
    batch = cache_get_json(_key(batch_no))
    if not isinstance(batch, dict) or batch.get("tenantId") != _tenant_id():
        raise not_found("导入批次不存在或已过期，请重新校验")
    return batch


def _safe_string(value, label: str, maximum: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}不能超过{maximum}字")
    if text.startswith(("=", "+", "@")):
        raise AppException("VALIDATION_ERROR", f"{label}疑似Excel公式，禁止导入")
    return text


def _positive_int(value, label: str) -> int:
    raw = str(value or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("VALIDATION_ERROR", f"{label}必须为有效正整数")
    return int(raw)


def _money(value, label: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}格式非法") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99"):
        raise AppException("VALIDATION_ERROR", f"{label}应在0至999999999999.99之间")
    if amount.as_tuple().exponent < -2:
        raise AppException("VALIDATION_ERROR", f"{label}最多保留2位小数")
    return amount


def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for index, raw in enumerate(rows, start=2):
        row = dict(raw or {})
        kind = _safe_string(row.get("bizType"), f"第{index}行业务类型", 30).upper()
        if kind not in _ALLOWED_TYPES:
            raise AppException("VALIDATION_ERROR", f"第{index}行业务类型非法")
        history_no = _safe_string(row.get("historyNo"), f"第{index}行历史编号", 100)
        if not history_no:
            raise AppException("VALIDATION_ERROR", f"第{index}行历史编号必填")
        student_id = _positive_int(row.get("studentId"), f"第{index}行学生ID")
        clean = {
            "bizType": kind,
            "historyNo": history_no,
            "studentId": student_id,
            "remark": _safe_string(row.get("remark"), f"第{index}行备注", 1000),
        }
        if kind == "DIFFICULT":
            level = _safe_string(row.get("level") or "GENERAL", "困难等级", 30).upper()
            if level not in _ALLOWED_AID_LEVELS:
                raise AppException("VALIDATION_ERROR", "困难等级非法")
            clean.update({"batchId": _positive_int(row.get("batchId"), "困难认定批次"), "level": level})
        elif kind == "FUNDING":
            clean.update({
                "batchId": _positive_int(row.get("batchId"), "资助批次"),
                "amount": str(_money(row.get("amount"), "资助金额") or ""),
            })
        elif kind == "DISCIPLINE":
            disc_type = _safe_string(row.get("discType") or "WARNING", "处分类型", 30).upper()
            if disc_type not in _ALLOWED_DISC_TYPES:
                raise AppException("VALIDATION_ERROR", "处分类型非法")
            reason = _safe_string(row.get("reason") or row.get("remark"), "违纪事实", 500)
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "历史处分违纪事实不少于5字")
            clean.update({
                "discType": disc_type,
                "reason": reason,
                "docNo": _safe_string(row.get("docNo"), "处分文号", 100),
            })
        elif kind == "DORM":
            clean["bedId"] = _positive_int(row.get("bedId"), "床位ID")
        elif kind == "ORG_CADRE":
            clean.update({
                "orgId": _positive_int(row.get("orgId"), "组织ID"),
                "position": _safe_string(row.get("position") or "成员", "职务", 100),
                "termCode": _safe_string(row.get("termCode"), "任期", 50),
            })
        else:
            stage = _safe_string(row.get("stage") or "APPLICANT", "党团阶段", 50).upper()
            if stage not in _ALLOWED_LEAGUE_STAGES:
                raise AppException("VALIDATION_ERROR", "党团发展阶段非法")
            dev_type = _safe_string(row.get("devType") or "PARTY", "发展类型", 20).upper()
            if dev_type not in ("PARTY", "LEAGUE"):
                raise AppException("VALIDATION_ERROR", "发展类型非法")
            clean.update({
                "stage": stage,
                "devType": dev_type,
                "branchName": _safe_string(row.get("branchName"), "支部名称", 100),
            })
        normalized.append(clean)
    return normalized


def _validate_references(rows: list[dict]) -> None:
    from app.models import AffairsStudentOrg, AidBatch, DormBed, FundingBatch, StudentProfile

    tenant_id = _tenant_id()
    db = get_sessionmaker()()
    try:
        student_ids = {row["studentId"] for row in rows}
        existing_students = set(db.scalars(select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.id.in_(student_ids or {-1}),
            StudentProfile.is_deleted.is_(False),
        )).all())
        missing = student_ids - existing_students
        if missing:
            raise AppException("DATA_CONFLICT", f"存在{len(missing)}名无有效主档学生")
        for row in rows:
            if row["bizType"] == "DIFFICULT":
                batch = db.get(AidBatch, row["batchId"])
                if not batch or batch.is_deleted or batch.tenant_id != tenant_id:
                    raise AppException("DATA_CONFLICT", f"困难认定批次{row['batchId']}不存在或跨租户")
            elif row["bizType"] == "FUNDING":
                batch = db.get(FundingBatch, row["batchId"])
                if not batch or batch.is_deleted or batch.tenant_id != tenant_id:
                    raise AppException("DATA_CONFLICT", f"资助批次{row['batchId']}不存在或跨租户")
            elif row["bizType"] == "DORM":
                bed = db.get(DormBed, row["bedId"])
                if not bed or bed.is_deleted or bed.tenant_id != tenant_id:
                    raise AppException("DATA_CONFLICT", f"床位{row['bedId']}不存在或跨租户")
            elif row["bizType"] == "ORG_CADRE":
                org = db.get(AffairsStudentOrg, row["orgId"])
                if not org or org.is_deleted or org.tenant_id != tenant_id:
                    raise AppException("DATA_CONFLICT", f"组织{row['orgId']}不存在或跨租户")
    finally:
        db.close()


def _confirm_rows(rows: list[dict]) -> dict:
    from app.models import (
        AffairsAuditTrail,
        AffairsLeagueDev,
        AffairsLeagueDevStage,
        AffairsOrgPosition,
        AidApply,
        DisciplineCase,
        DormBed,
        FundingApplication,
        FundingBatch,
        StudentProfile,
        StudentStageEvent,
    )
    from app.services import affairs_discipline_service as discipline
    from app.services import affairs_dorm_service as dorm

    tenant_id = _tenant_id()
    actor = get_current_user_ctx() or {}
    raw_actor = str(actor.get("userId") or "").removeprefix("db-")
    created_by = int(raw_actor) if raw_actor.isdigit() else None
    db = get_sessionmaker()()
    inserted, records = 0, []
    try:
        history_nos = {f"historyNo={row['historyNo']}" for row in rows}
        existing = set(db.scalars(select(AffairsAuditTrail.detail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type.like("HISTORY_IMPORT_%"),
            AffairsAuditTrail.detail.in_(history_nos),
            AffairsAuditTrail.action == "IMPORT",
            AffairsAuditTrail.is_deleted.is_(False),
        )).all())
        if existing:
            raise AppException("DATA_CONFLICT", "批次包含已导入历史编号，请重新执行Dry-Run")

        for row in rows:
            kind, student_id = row["bizType"], int(row["studentId"])
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.id == student_id,
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("学生主档不存在")
            common = {"tenant_id": tenant_id, "created_by": created_by}
            if kind == "DIFFICULT":
                obj = AidApply(
                    **common,
                    batch_id=row["batchId"],
                    student_id=student_id,
                    apply_level=row["level"],
                    final_level=row["level"],
                    statement=row["remark"] or "历史迁移",
                    status="APPROVED",
                )
                db.add(obj)
                db.flush()
                stage = "AID_APPROVED"
            elif kind == "FUNDING":
                batch = db.get(FundingBatch, row["batchId"])
                obj = FundingApplication(
                    **common,
                    batch_id=batch.id,
                    student_id=student_id,
                    project_type=batch.project_type,
                    amount=Decimal(row["amount"]) if row["amount"] else None,
                    statement=row["remark"] or "历史迁移",
                    status="GRANTED",
                )
                db.add(obj)
                db.flush()
                stage = "FUNDING_GRANTED"
            elif kind == "DISCIPLINE":
                obj = DisciplineCase(
                    **common,
                    student_id=student_id,
                    disc_type=row["discType"],
                    reason=row["reason"],
                    doc_no=row["docNo"] or None,
                    status="EFFECTIVE",
                    effective_at=datetime.utcnow(),
                )
                db.add(obj)
                db.flush()
                discipline._make_effective(db, obj, student)
                stage = "DISCIPLINE_EFFECTIVE"
            elif kind == "DORM":
                from app.models import DormBuilding, DormRoom

                target = db.scalars(select(DormBed).where(
                    DormBed.tenant_id == tenant_id,
                    DormBed.id == row["bedId"],
                    DormBed.is_deleted.is_(False),
                ).with_for_update()).first()
                current = db.scalars(select(DormBed).where(
                    DormBed.tenant_id == tenant_id,
                    DormBed.student_id == student_id,
                    DormBed.status == "OCCUPIED",
                    DormBed.is_deleted.is_(False),
                ).with_for_update()).all()
                if target.student_id not in (None, student_id) or target.status not in ("VACANT", "OCCUPIED"):
                    raise AppException("DATA_CONFLICT", f"床位{target.id}已被其他学生占用")
                for old in current:
                    if old.id != target.id:
                        old.student_id, old.status, old.occupied_at = None, "VACANT", None
                        old.cs_dorm_record_id = None
                        old.version = int(old.version or 0) + 1
                building = db.get(DormBuilding, int(target.building_id))
                room = db.get(DormRoom, int(target.room_id))
                if not building or not room or building.tenant_id != tenant_id or room.tenant_id != tenant_id:
                    raise AppException("DATA_INCONSISTENT", "床位楼栋/房间关系异常")
                target.student_id, target.status, target.occupied_at = student_id, "OCCUPIED", datetime.utcnow()
                target.version = int(target.version or 0) + 1
                target.cs_dorm_record_id = dorm._writeback_dorm_record(
                    db, student_id, building.building_name, room.room_no, target.bed_no,
                )
                obj = target
                stage = "DORM_CHECKIN"
            elif kind == "ORG_CADRE":
                duplicate = db.scalars(select(AffairsOrgPosition.id).where(
                    AffairsOrgPosition.tenant_id == tenant_id,
                    AffairsOrgPosition.org_id == row["orgId"],
                    AffairsOrgPosition.student_id == student_id,
                    AffairsOrgPosition.position == row["position"],
                    AffairsOrgPosition.status == "ACTIVE",
                    AffairsOrgPosition.is_deleted.is_(False),
                )).first()
                if duplicate:
                    raise AppException("DATA_CONFLICT", "该学生已有相同组织任职")
                obj = AffairsOrgPosition(
                    **common,
                    org_id=row["orgId"],
                    student_id=student_id,
                    position=row["position"],
                    term_code=row["termCode"] or None,
                    status="ACTIVE",
                )
                db.add(obj)
                db.flush()
                stage = "ORG_CADRE_ACTIVE"
            else:
                duplicate = db.scalars(select(AffairsLeagueDev.id).where(
                    AffairsLeagueDev.tenant_id == tenant_id,
                    AffairsLeagueDev.student_id == student_id,
                    AffairsLeagueDev.dev_type == row["devType"],
                    AffairsLeagueDev.status == "ONGOING",
                    AffairsLeagueDev.is_deleted.is_(False),
                )).first()
                if duplicate:
                    raise AppException("DATA_CONFLICT", "该学生已有进行中的同类党团发展记录")
                obj = AffairsLeagueDev(
                    **common,
                    student_id=student_id,
                    dev_type=row["devType"],
                    current_stage=row["stage"],
                    branch_name=row["branchName"] or None,
                    status="ONGOING",
                )
                db.add(obj)
                db.flush()
                db.add(AffairsLeagueDevStage(
                    tenant_id=tenant_id,
                    dev_id=obj.id,
                    to_stage=row["stage"],
                    operator="历史迁移",
                    remark=f"historyNo={row['historyNo']}",
                ))
                stage = "LEAGUE_HISTORY_IMPORTED"

            db.add(StudentStageEvent(
                tenant_id=tenant_id,
                student_id=student_id,
                from_stage=None,
                to_stage=stage,
                reason="学工历史迁移",
                source_module="student-affairs",
            ))
            db.add(AffairsAuditTrail(
                tenant_id=tenant_id,
                biz_type=f"HISTORY_IMPORT_{kind}",
                biz_id=obj.id,
                action="IMPORT",
                operator=str(actor.get("realName") or "未记录"),
                detail=f"historyNo={row['historyNo']}",
                occurred_at=datetime.utcnow(),
            ))
            records.append({"historyNo": row["historyNo"], "bizType": kind, "recordId": str(obj.id)})
            inserted += 1
        db.commit()
        return {"insertedRows": inserted, "reconciliation": {"records": records}}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import domain_import_service as service

    old_dry_run = service.dry_run
    old_peek = service.peek_batch
    old_assert = service.assert_confirm_allowed
    old_confirm = service.confirm

    def dry_run(domain, rows, *, namespace=None, user=None):
        result = old_dry_run(domain, rows, namespace=namespace, user=user)
        if domain != "student-affairs":
            return result
        batch_no = result["batchNo"]
        memory = service._MEM.pop(batch_no, None)
        if not memory:
            raise AppException("SERVER_ERROR", "Dry-Run批次生成失败")
        normalized = _normalize_rows(memory.get("rows") or [])
        _validate_references(normalized)
        memory["rows"] = normalized
        memory["status"] = "DRY_RUN_PASSED"
        _persist(batch_no, memory)
        result.update({"status": "DRY_RUN_PASSED", "okRows": len(normalized), "errorRows": 0, "errors": []})
        return result

    def peek_batch(batch_no):
        try:
            batch = _load(batch_no)
            return {
                "domain": batch.get("domain"),
                "status": batch.get("status"),
                "createdBy": batch.get("createdBy"),
            }
        except Exception:
            return old_peek(batch_no)

    def assert_confirm_allowed(user, batch_no, auth):
        try:
            batch = _load(batch_no)
        except Exception:
            return old_assert(user, batch_no, auth)
        from app.core.import_export_auth import assert_import_batch_owner

        assert_import_batch_owner(user, batch.get("createdBy"), auth.import_perm)

    def confirm(batch_no):
        try:
            batch = _load(batch_no)
        except Exception:
            return old_confirm(batch_no)
        if batch.get("domain") != "student-affairs":
            return old_confirm(batch_no)
        if batch.get("status") != "DRY_RUN_PASSED":
            raise AppException("DATA_CONFLICT", "该批次不是可确认状态")
        acquired = cache_set_json_if_absent(
            _lock_key(batch_no), {"startedAt": datetime.utcnow().isoformat()}, 300,
        )
        if acquired is None:
            raise AppException("IMPORT_STORE_UNAVAILABLE", "历史导入分布式锁不可用", http_status=503)
        if not acquired:
            raise AppException("DATA_CONFLICT", "该导入批次正在确认或已被其他请求处理")
        try:
            batch["status"] = "PROCESSING"
            _persist(batch_no, batch)
            result = _confirm_rows(batch.get("rows") or [])
            batch["status"] = "SUCCESS"
            batch["result"] = result
            _persist(batch_no, batch)
            return {"batchNo": batch_no, "status": "SUCCESS", **result}
        except Exception:
            batch["status"] = "FAILED"
            _persist(batch_no, batch)
            raise
        finally:
            cache_delete(_lock_key(batch_no))

    service.dry_run = dry_run
    service.peek_batch = peek_batch
    service.assert_confirm_allowed = assert_confirm_allowed
    service.confirm = confirm
    _INSTALLED = True
