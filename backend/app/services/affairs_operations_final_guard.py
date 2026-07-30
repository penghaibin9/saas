"""学工材料与安全批次终态安全门。

- 材料审核附件授权已迁移到公共文件 resolver registry；
- 教师材料队列在计数和分页前按业务权限过滤，禁止跨域数量泄露；
- 宿管的调宿材料按当前入住楼栋或调宿目标楼栋收敛，不错误套用班级范围；
- 批次幂等键绑定同一请求，失败尝试次数即使事务回滚也可靠累计；
- 材料重新开启新一轮时仅保留历史版本，不把旧验收件冒充本轮当前件。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_INSTALLED = False


def _install_dorm_material_scope_guard(operations) -> None:
    """DORM_BUILDING 角色按楼栋关联学生，而不是按空班级集合 fail-closed。"""
    original = operations._require_student_scope

    def require_student_scope(db, student_id: int, user: dict) -> None:
        from app.core.affairs_security import build_affairs_context, no_data_scope
        from app.models import DormBed, DormTransfer

        ctx = build_affairs_context(user or {}, db)
        if ctx.scope_type != "DORM_BUILDING":
            original(db, student_id, user)
            return
        buildings = set(ctx.dorm_building_ids or set())
        if not buildings:
            raise no_data_scope("未配置宿舍楼栋数据范围")
        current = db.scalar(select(DormBed.id).where(
            DormBed.tenant_id == _tid(),
            DormBed.student_id == int(student_id),
            DormBed.building_id.in_(buildings),
            DormBed.status == "OCCUPIED",
            DormBed.is_deleted.is_(False),
        ).limit(1))
        if current:
            return
        target = db.scalar(select(DormTransfer.id).join(
            DormBed, DormBed.id == DormTransfer.to_bed_id,
        ).where(
            DormTransfer.tenant_id == _tid(),
            DormTransfer.student_id == int(student_id),
            DormTransfer.is_deleted.is_(False),
            DormTransfer.status.in_((
                "SUBMITTED", "COUNSELOR_REVIEW", "DORM_REVIEW",
                "DORM_MANAGER_REVIEW", "RETURNED",
            )),
            DormBed.tenant_id == _tid(),
            DormBed.building_id.in_(buildings),
            DormBed.is_deleted.is_(False),
        ).limit(1))
        if not target:
            raise no_data_scope("该学生的住宿或调宿记录不在您的楼栋范围内")

    operations._require_student_scope = require_student_scope


def _install_material_file_access_guard(_operations) -> None:
    """阶段 2 兼容空入口：MATERIAL_REQUIREMENT 已由 resolver registry 授权。"""
    return


def _install_teacher_requirement_scope_guard(operations) -> None:
    def list_teacher_requirements(
        user: dict,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        from app.core.affairs_security import build_affairs_context
        from app.models import DormBed, DormTransfer, StudentProfile, User
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.services.affairs_dashboard_service import _allowed_class_ids

        visible_biz_types = {
            biz_type
            for biz_type, permissions in operations._BIZ_PERMISSIONS.items()
            if any(has_permission(user or {}, code) for code in permissions)
        }
        if not visible_biz_types:
            return [], 0
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        with session() as db:
            ctx = build_affairs_context(user or {}, db)
            conds = [
                AffairsMaterialRequirement.tenant_id == _tid(),
                AffairsMaterialRequirement.biz_type.in_(visible_biz_types),
                AffairsMaterialRequirement.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == AffairsMaterialRequirement.student_id,
                StudentProfile.is_deleted.is_(False),
            ]
            if status:
                conds.append(AffairsMaterialRequirement.status == str(status).upper())
            if ctx.scope_type == "DORM_BUILDING":
                visible_biz_types &= {"DORM_TRANSFER"}
                if not visible_biz_types or not ctx.dorm_building_ids:
                    return [], 0
                conds[1] = AffairsMaterialRequirement.biz_type.in_(visible_biz_types)
                current_students = select(DormBed.student_id).where(
                    DormBed.tenant_id == _tid(),
                    DormBed.building_id.in_(ctx.dorm_building_ids),
                    DormBed.status == "OCCUPIED",
                    DormBed.is_deleted.is_(False),
                )
                target_students = select(DormTransfer.student_id).join(
                    DormBed, DormBed.id == DormTransfer.to_bed_id,
                ).where(
                    DormTransfer.tenant_id == _tid(),
                    DormTransfer.is_deleted.is_(False),
                    DormTransfer.status.in_((
                        "SUBMITTED", "COUNSELOR_REVIEW", "DORM_REVIEW",
                        "DORM_MANAGER_REVIEW", "RETURNED",
                    )),
                    DormBed.tenant_id == _tid(),
                    DormBed.building_id.in_(ctx.dorm_building_ids),
                    DormBed.is_deleted.is_(False),
                )
                conds.append(or_(
                    StudentProfile.id.in_(current_students),
                    StudentProfile.id.in_(target_students),
                ))
            else:
                allowed, _ = _allowed_class_ids(db, user)
                if allowed is not None:
                    conds.append(StudentProfile.class_id.in_(allowed or {-1}))
            joined = select(AffairsMaterialRequirement).join(
                StudentProfile,
                StudentProfile.id == AffairsMaterialRequirement.student_id,
            )
            total = int(db.scalar(
                select(func.count()).select_from(AffairsMaterialRequirement).join(
                    StudentProfile,
                    StudentProfile.id == AffairsMaterialRequirement.student_id,
                ).where(*conds)
            ) or 0)
            rows = db.scalars(
                joined.where(*conds)
                .order_by(AffairsMaterialRequirement.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            submissions = operations._submission_rows(db, [row.id for row in rows])
            owner_ids = {int(row.review_owner_id) for row in rows if row.review_owner_id}
            owners = {
                int(owner.id): owner.real_name
                for owner in db.scalars(select(User).where(
                    User.tenant_id == _tid(),
                    User.id.in_(owner_ids or {-1}),
                    User.is_deleted.is_(False),
                )).all()
            }
            items = [
                operations._requirement_dict(
                    row,
                    submissions.get(int(row.id), []),
                    student_view=False,
                    owner_name=owners.get(int(row.review_owner_id or 0), ""),
                )
                for row in rows
            ]
            return items, total

    operations.list_teacher_requirements = list_teacher_requirements


def _install_batch_reliability_guard(operations) -> None:
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem

    original_create_batch = operations.create_batch_job
    original_execute_item = operations._execute_batch_item
    original_audit = operations._audit

    def audit(db, biz_id: int, action: str, detail: str = "") -> None:
        if not str(action or "").startswith("BATCH_"):
            original_audit(db, biz_id, action, detail)
            return
        from app.models import AffairsAuditTrail

        user = get_current_user_ctx() or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(),
            biz_type="BATCH_JOB",
            biz_id=int(biz_id),
            action=action,
            operator=user.get("realName") or operations._user_key(user),
            role_name=user.get("currentRoleCode") or "",
            detail=(detail or "")[:1000],
            occurred_at=datetime.utcnow(),
        ))

    def _request_ids(payload: dict) -> list[int]:
        items = payload.get("items") or []
        versions = [item.get("version") for item in items]
        if any(
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 0
            for version in versions
        ):
            raise AppException("VALIDATION_ERROR", "批量提醒每一条都必须携带当前材料版本")
        return [int(item.get("requirementId") or 0) for item in items]

    def _assert_same_request(job, requested_ids: list[int]) -> None:
        stored = [int(value) for value in ((job.request_json or {}).get("requirementIds") or [])]
        if stored != requested_ids:
            raise AppException("IDEMPOTENCY_CONFLICT", "同一幂等键不能用于不同的批次记录")

    def create_batch_job(user: dict, payload: dict) -> dict:
        requested_ids = _request_ids(payload)
        job_type = str(payload.get("jobType") or "").strip().upper()
        key = str(payload.get("idempotencyKey") or "").strip()
        resume_id = None
        with session() as db:
            existed = db.scalars(select(AffairsBatchJob).where(
                AffairsBatchJob.tenant_id == _tid(),
                AffairsBatchJob.job_type == job_type,
                AffairsBatchJob.idempotency_key == key,
                AffairsBatchJob.is_deleted.is_(False),
            )).first()
            if existed:
                _assert_same_request(existed, requested_ids)
                if existed.status == "PENDING":
                    resume_id = int(existed.id)
                else:
                    return operations._batch_job_dict(db, existed)
        if resume_id:
            return operations.run_batch_job(resume_id, user)
        result = original_create_batch(user, payload)
        result_id = str(result.get("batchJobId") or "")
        if result_id.isdigit():
            with session() as db:
                job = db.get(AffairsBatchJob, int(result_id))
                if job and job.tenant_id == _tid() and not job.is_deleted:
                    _assert_same_request(job, requested_ids)
        return result

    def execute_batch_item(item_id: int, user: dict) -> None:
        before = 0
        with session() as db:
            row = db.get(AffairsBatchJobItem, int(item_id))
            if row and row.tenant_id == _tid() and not row.is_deleted:
                before = int(row.attempt_count or 0)
        original_execute_item(item_id, user)
        with session() as db:
            row = db.scalars(select(AffairsBatchJobItem).where(
                AffairsBatchJobItem.tenant_id == _tid(),
                AffairsBatchJobItem.id == int(item_id),
                AffairsBatchJobItem.is_deleted.is_(False),
            ).with_for_update()).first()
            if row and row.status == "FAILED" and int(row.attempt_count or 0) <= before:
                row.attempt_count = before + 1
                row.started_at = row.started_at or row.completed_at or datetime.utcnow()
                row.version = int(row.version or 0) + 1
                db.commit()

    operations._audit = audit
    operations.create_batch_job = create_batch_job
    operations._execute_batch_item = execute_batch_item


def _install_material_round_guard(operations) -> None:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement

    original = operations.create_material_requirement

    def create_material_requirement(user: dict, payload: dict) -> dict:
        result = original(user, payload)
        requirement_id = str(result.get("requirementId") or "")
        if (
            result.get("created")
            or result.get("status") != "MISSING"
            or not result.get("currentSubmissionId")
        ):
            return result
        if not requirement_id.isdigit():
            return result
        with session() as db:
            row = db.scalars(select(AffairsMaterialRequirement).where(
                AffairsMaterialRequirement.tenant_id == _tid(),
                AffairsMaterialRequirement.id == int(requirement_id),
                AffairsMaterialRequirement.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row or row.status != "MISSING" or not row.current_submission_id:
                return result
            row.current_submission_id = None
            row.version = int(row.version or 0) + 1
            db.commit()
            db.refresh(row)
            submissions = operations._submission_rows(db, [row.id]).get(int(row.id), [])
            owner = db.get(User, int(row.review_owner_id)) if row.review_owner_id else None
            refreshed = operations._requirement_dict(
                row,
                submissions,
                student_view=False,
                owner_name=(owner.real_name if owner else ""),
            )
            refreshed["created"] = False
            return refreshed

    operations.create_material_requirement = create_material_requirement


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_operations_service as operations

    _install_dorm_material_scope_guard(operations)
    _install_material_file_access_guard(operations)
    _install_teacher_requirement_scope_guard(operations)
    _install_batch_reliability_guard(operations)
    _install_material_round_guard(operations)
    _INSTALLED = True
