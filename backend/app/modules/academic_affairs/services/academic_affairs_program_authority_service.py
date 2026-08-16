"""A-W2 培养方案绑定与版本 Authority。

只接管三类必须串行/必须 fail-closed 的高风险动作：
- bind_grade：专业年级 fallback 与班级 override 分 scope 生效；
- create_new_version：一个源版本只能有一个直接后继，且完整复制方案定义快照；
- list_program_versions：历史版本链出现 fork/cycle 时拒绝猜测。

其它培养方案 CRUD/审核/生命周期继续由 ``academic_affairs_program_core_service`` 提供。
本模块不新增表、不依赖 import monkey-patch；公开 facade 显式调用这里。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_core_service as _core


_BINDABLE_STATUSES = ("PUBLISHED", "ENABLED")
_VERSIONABLE_STATUSES = ("PUBLISHED", "ENABLED", "FROZEN", "DISABLED")


def _program_for_update(db, program_id: int):
    from app.models import AaProgram

    program = db.scalars(
        select(AaProgram).where(
            AaProgram.id == int(program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).with_for_update()
    ).first()
    if not program:
        raise not_found("培养方案不存在")
    return program


def _class_scope_anchor(db, *, program, grade_year: str, class_id: int):
    from app.models import SchoolClass

    clazz = db.scalars(
        select(SchoolClass).where(
            SchoolClass.id == int(class_id),
            SchoolClass.tenant_id == _tid(),
            SchoolClass.is_deleted.is_(False),
        ).with_for_update()
    ).first()
    if not clazz:
        raise AppException("DATA_CONFLICT", "班级不存在或不属于当前学校", http_status=409)
    if not program.major_id or int(clazz.major_id) != int(program.major_id):
        raise AppException("DATA_CONFLICT", "班级所属专业与培养方案专业不一致", http_status=409)
    if str(clazz.grade or "") != str(grade_year):
        raise AppException("DATA_CONFLICT", "班级年级与方案绑定年级不一致", http_status=409)
    if str(clazz.class_status or "").upper() != "NORMAL":
        raise AppException("DATA_CONFLICT", "仅正常在读班级可作为培养方案班级特例", http_status=409)
    return clazz


def _major_scope_anchor(db, *, program):
    from app.models import Major

    if not program.major_id:
        raise AppException("DATA_CONFLICT", "培养方案未设置专业，不能绑定年级", http_status=409)
    major = db.scalars(
        select(Major).where(
            Major.id == int(program.major_id),
            Major.tenant_id == _tid(),
            Major.is_deleted.is_(False),
        ).with_for_update()
    ).first()
    if not major:
        raise AppException("DATA_CONFLICT", "培养方案专业不存在或不属于当前学校", http_status=409)
    return major


def bind_grade(program_id, user, grade_year, class_id=None) -> dict:
    """绑定已发布方案。

    Major+grade 是通用 fallback；classId 是更高优先级 override。两种 scope 可以同时 ACTIVE，
    只 supersede 同 scope 的旧绑定。scope anchor 使用真实 Major/SchoolClass 行锁，因此同一 scope
    的并发写会串行，最终最多一个 ACTIVE。
    """
    grade = str(grade_year or "").strip()
    if not grade:
        raise AppException("VALIDATION_ERROR", "绑定年级必填")

    with session() as db:
        from app.models import AaProgramBinding

        program = _program_for_update(db, int(program_id))
        if program.status not in _BINDABLE_STATUSES:
            raise AppException("DATA_CONFLICT", "仅已发布/已启用方案可绑定年级")

        class_value = None
        if class_id not in (None, ""):
            try:
                class_value = int(class_id)
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", "班级ID非法") from exc
            clazz = _class_scope_anchor(
                db,
                program=program,
                grade_year=grade,
                class_id=class_value,
            )
            scope_clause = AaProgramBinding.class_id == clazz.id
            scope_label = f"class={clazz.id}"
        else:
            _major_scope_anchor(db, program=program)
            scope_clause = AaProgramBinding.class_id.is_(None)
            scope_label = "major-grade"

        previous = db.scalars(
            select(AaProgramBinding).where(
                AaProgramBinding.tenant_id == _tid(),
                AaProgramBinding.major_id == int(program.major_id),
                AaProgramBinding.grade_year == grade,
                scope_clause,
                AaProgramBinding.status == "ACTIVE",
                AaProgramBinding.is_deleted.is_(False),
            ).with_for_update()
        ).all()
        for row in previous:
            row.status = "SUPERSEDED"

        binding = AaProgramBinding(
            tenant_id=_tid(),
            program_id=program.id,
            major_id=int(program.major_id),
            grade_year=grade,
            class_id=class_value,
            bound_at=datetime.utcnow(),
            status="ACTIVE",
        )
        db.add(binding)
        program.status = "ENABLED"
        _core._audit(db, program.id, "BIND", f"grade={grade};scope={scope_label}")
        db.commit()
        db.refresh(program)
        return {
            "programId": str(program.id),
            "gradeYear": grade,
            "classId": str(class_value) if class_value is not None else "",
            "status": program.status,
        }


def create_new_version(program_id, user, reason=None) -> dict:
    """从一个稳定源版本创建唯一直接后继，并复制完整的方案定义快照。"""
    if reason is not None:
        reason = reason.strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")

    with session() as db:
        from app.models import (
            AaProgram,
            AaProgramCourse,
            AaProgramGraduationRequirement as Req,
            AaProgramPracticeSegment as Seg,
        )

        old = _program_for_update(db, int(program_id))
        if old.status not in _VERSIONABLE_STATUSES:
            raise AppException("DATA_CONFLICT", "仅已发布/启用/冻结/停用方案可新建版本（编制/退回态直接编辑即可）")

        successors = db.scalars(
            select(AaProgram).where(
                AaProgram.tenant_id == _tid(),
                AaProgram.prev_version_id == old.id,
                AaProgram.is_deleted.is_(False),
            ).with_for_update()
        ).all()
        if successors:
            raise AppException(
                "DATA_CONFLICT",
                "当前版本已存在后继版本，请从最新版本继续变更，禁止从同一源版本分叉",
                details={
                    "programId": str(old.id),
                    "successorProgramIds": [str(row.id) for row in successors],
                },
                http_status=409,
            )

        new_program = AaProgram(
            tenant_id=_tid(),
            program_name=old.program_name,
            major_id=old.major_id,
            grade_year=old.grade_year,
            total_credits=old.total_credits,
            requirement_json=old.requirement_json,
            version=old.version + 1,
            prev_version_id=old.id,
            status="DRAFT",
        )
        db.add(new_program)
        db.flush()

        courses = db.scalars(select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id == old.id,
            AaProgramCourse.is_deleted.is_(False),
        )).all()
        for course in courses:
            db.add(AaProgramCourse(
                tenant_id=_tid(),
                program_id=new_program.id,
                course_id=course.course_id,
                course_name=course.course_name,
                open_term_no=course.open_term_no,
                module=course.module,
                credit_snapshot=course.credit_snapshot,
            ))

        requirements = db.scalars(select(Req).where(
            Req.tenant_id == _tid(),
            Req.program_id == old.id,
            Req.is_deleted.is_(False),
            Req.status == "ACTIVE",
        )).all()
        for requirement in requirements:
            db.add(Req(
                tenant_id=_tid(),
                program_id=new_program.id,
                category=requirement.category,
                content=requirement.content,
                sort_order=requirement.sort_order,
                status="ACTIVE",
            ))

        practices = db.scalars(select(Seg).where(
            Seg.tenant_id == _tid(),
            Seg.program_id == old.id,
            Seg.is_deleted.is_(False),
            Seg.status == "ACTIVE",
        )).all()
        for practice in practices:
            db.add(Seg(
                tenant_id=_tid(),
                program_id=new_program.id,
                segment_name=practice.segment_name,
                segment_type=practice.segment_type,
                open_term_no=practice.open_term_no,
                weeks=practice.weeks,
                credit=practice.credit,
                org_mode=practice.org_mode,
                location=practice.location,
                assessment_mode=practice.assessment_mode,
                sort_order=practice.sort_order,
                status="ACTIVE",
            ))

        if reason:
            _core._audit(
                db,
                new_program.id,
                "CHANGE_NEW_VERSION",
                f"reason={reason};fromProgramId={old.id},fromVersion={old.version}",
            )
        else:
            _core._audit(
                db,
                new_program.id,
                "NEW_VERSION",
                f"fromProgramId={old.id},fromVersion={old.version}",
            )
        db.commit()
        db.refresh(new_program)
        return _core._row(new_program)


def list_program_versions(program_id, user):
    """返回线性版本链；断链、cycle 或一个节点存在多个后继时 fail-closed。"""
    with session() as db:
        from app.models import AaProgram

        current = db.scalars(select(AaProgram).where(
            AaProgram.id == int(program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        )).first()
        if not current:
            raise not_found("培养方案不存在")

        root = current
        seen = {root.id}
        while root.prev_version_id:
            if int(root.prev_version_id) in seen:
                raise AppException("DATA_CONFLICT", "培养方案版本链存在循环，禁止猜测版本顺序", http_status=409)
            parent = db.scalars(select(AaProgram).where(
                AaProgram.id == int(root.prev_version_id),
                AaProgram.tenant_id == _tid(),
                AaProgram.is_deleted.is_(False),
            )).first()
            if not parent:
                raise AppException("DATA_CONFLICT", "培养方案版本链断裂，缺少前置版本", http_status=409)
            root = parent
            seen.add(root.id)

        chain = [root]
        seen = {root.id}
        cursor = root
        while True:
            successors = db.scalars(select(AaProgram).where(
                AaProgram.tenant_id == _tid(),
                AaProgram.prev_version_id == cursor.id,
                AaProgram.is_deleted.is_(False),
            ).order_by(AaProgram.id)).all()
            if len(successors) > 1:
                raise AppException(
                    "DATA_CONFLICT",
                    "培养方案版本链存在多个直接后继，禁止静默选择其中一个",
                    details={
                        "programId": str(cursor.id),
                        "successorProgramIds": [str(row.id) for row in successors],
                    },
                    http_status=409,
                )
            if not successors:
                break
            nxt = successors[0]
            if nxt.id in seen:
                raise AppException("DATA_CONFLICT", "培养方案版本链存在循环，禁止猜测版本顺序", http_status=409)
            chain.append(nxt)
            seen.add(nxt.id)
            cursor = nxt

        return [
            dict(
                _core._row(program),
                canNewVersion=program.status in _VERSIONABLE_STATUSES,
                isCurrent=program.id == current.id,
            )
            for program in chain
        ]
