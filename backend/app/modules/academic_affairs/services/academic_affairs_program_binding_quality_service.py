"""V2-01 培养方案绑定完整性最终层。

补足基础校验器无法单表判断的全局规则：
- 同一专业/年级/班级不可同时存在多个生效方案；
- 班级特例必须属于本租户且与绑定专业、年级一致；
- 指向停用/删除班级的绑定阻断提交和任务生成。
"""
from __future__ import annotations

from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_final_service as _base


def __getattr__(name):
    return getattr(_base, name)


def validate_program_db(db, program_id: int) -> dict:
    from app.models import AaProgram, AaProgramBinding, SchoolClass

    result = _base.validate_program_db(db, program_id)
    program = db.query(AaProgram).filter(
        AaProgram.id == int(program_id),
        AaProgram.tenant_id == _tid(),
        AaProgram.is_deleted.is_(False),
    ).first()
    bindings = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.program_id == int(program_id),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    ).all()

    for binding in bindings:
        route = f"/admin/academic-affairs/programs/{program_id}"
        if binding.class_id:
            clazz = db.query(SchoolClass).filter(
                SchoolClass.id == int(binding.class_id),
                SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False),
            ).first()
            if not clazz:
                result["issues"].append(_base._base._issue(
                    "BINDING_CLASS_NOT_FOUND", "BLOCKER",
                    f"班级特例绑定指向不存在或已删除班级：{binding.class_id}",
                    object_id=binding.id, field_path="bindings.classId",
                    suggestion="删除失效绑定或重新选择本校班级", fix_route=route,
                ))
            else:
                if binding.major_id and clazz.major_id and int(binding.major_id) != int(clazz.major_id):
                    result["issues"].append(_base._base._issue(
                        "BINDING_CLASS_MAJOR_MISMATCH", "BLOCKER",
                        f"班级“{clazz.class_name}”所属专业与方案绑定专业不一致",
                        object_id=binding.id, field_path="bindings.classId",
                        suggestion="修正班级特例或专业绑定", fix_route=route,
                    ))
                if binding.grade_year and str(clazz.grade or "") != str(binding.grade_year):
                    result["issues"].append(_base._base._issue(
                        "BINDING_CLASS_GRADE_MISMATCH", "BLOCKER",
                        f"班级“{clazz.class_name}”年级与方案绑定年级不一致",
                        object_id=binding.id, field_path="bindings.gradeYear",
                        suggestion="修正绑定年级或选择正确班级", fix_route=route,
                    ))
                if str(clazz.class_status or "").upper() != "NORMAL":
                    result["issues"].append(_base._base._issue(
                        "BINDING_CLASS_INACTIVE", "BLOCKER",
                        f"班级“{clazz.class_name}”当前状态为 {clazz.class_status}，不可作为生效方案绑定",
                        object_id=binding.id, field_path="bindings.classId",
                        suggestion="选择正常在用班级或停用该绑定", fix_route=route,
                    ))

        conflicts = db.query(AaProgramBinding, AaProgram).join(
            AaProgram, AaProgram.id == AaProgramBinding.program_id,
        ).filter(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.program_id != int(program_id),
            AaProgramBinding.major_id == binding.major_id,
            AaProgramBinding.grade_year == binding.grade_year,
            AaProgramBinding.class_id.is_(None) if binding.class_id is None else AaProgramBinding.class_id == binding.class_id,
            AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
            AaProgram.tenant_id == _tid(),
            AaProgram.status.in_(["PUBLISHED", "ENABLED", "FROZEN"]),
            AaProgram.is_deleted.is_(False),
        ).all()
        if conflicts:
            names = "、".join(str(other_program.program_name) for _other_binding, other_program in conflicts[:3])
            result["issues"].append(_base._base._issue(
                "ACTIVE_BINDING_CROSS_PROGRAM_CONFLICT", "BLOCKER",
                f"同一专业年级/班级已被其它生效方案绑定：{names}",
                object_id=binding.id, field_path="bindings",
                suggestion="只保留一个生效方案，旧版本改为SUPERSEDED或停用", fix_route=route,
            ))

    return _base._refresh_summary(result)


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        return validate_program_db(db, program_id)
