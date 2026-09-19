"""Current organization references shared with existing class lifecycle rules.

This is an inspection snapshot, not authorization to apply a later change.
It intentionally returns counts and guidance, never student/teacher identities.
"""
from datetime import datetime
from sqlalchemy import and_, or_, select
from app.services.org_class_lifecycle_service import (
    EXITED_STUDENT_STATUSES, read_class_references, read_teaching_references, task_blocks_closure,
)


def _ref(kind, label, count, guidance):
    return {'refType': kind, 'label': label, 'refCount': count, 'blocked': count > 0, 'guidance': guidance}


def check_org_references(db, tenant_id, kind, node):
    from app.models import College, Major, SchoolClass, StudentProfile, AaTeachingTask, AaTeachingTaskBatch, AaTerm, AaProgram, AaProgramBinding, AaProgramCourse
    from app.modules.academic_affairs.services.academic_affairs_program_transition_service import _PROGRAM_USABLE

    warnings = []
    if kind == 'CLASS':
        students, tasks, counts, task_counts = read_class_references(db, tenant_id, [node.id], lock=False)
        student_count, task_count = counts.get(node.id, 0), task_counts.get(node.id, 0)
        refs = []
        if node.counselor_id or node.head_teacher_id:
            warnings.append('该班仍有班主任或辅导员绑定，请结合后续带班安排核对。')
        major = db.scalar(select(Major).where(Major.tenant_id == tenant_id, Major.id == node.major_id))
        college = db.scalar(select(College).where(College.tenant_id == tenant_id, College.id == major.college_id)) if major else None
        if not major or major.is_deleted or major.status != 'ACTIVE' or not college or college.is_deleted or college.status != 'ACTIVE':
            refs.append(_ref('PARENT_UNAVAILABLE', '上级组织不可用', 1, '先核对所属专业、学院的归属和启用状态。'))
        name = node.class_name
    else:
        majors = db.scalars(select(Major).where(Major.tenant_id == tenant_id,
            Major.college_id == node.id if kind == 'COLLEGE' else Major.id == node.id)).all()
        major_ids = [row.id for row in majors]
        classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
            SchoolClass.major_id.in_(major_ids))).all()
        class_ids = [row.id for row in classes]
        student_condition = or_(StudentProfile.major_id.in_(major_ids), StudentProfile.class_id.in_(class_ids))
        if kind == 'COLLEGE':
            student_condition = or_(student_condition, StudentProfile.college_id == node.id)
        students = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False), student_condition)).all()
        student_count = sum(row.student_status not in EXITED_STUDENT_STATUSES for row in students)
        # Include tasks not yet assigned to a class when exact program-course
        # provenance identifies this major; college-owned batches also count.
        program_ids = select(AaProgram.id).where(AaProgram.tenant_id == tenant_id, AaProgram.major_id.in_(major_ids))
        source_courses = select(AaProgramCourse.id).where(AaProgramCourse.tenant_id == tenant_id,
            AaProgramCourse.program_id.in_(program_ids))
        task_condition = or_(AaTeachingTask.class_id.in_(class_ids), AaTeachingTask.source_program_course_id.in_(source_courses))
        if kind == 'COLLEGE':
            task_condition = or_(task_condition, AaTeachingTaskBatch.college_id == node.id)
        tasks = read_teaching_references(db, tenant_id, task_condition, lock=False)
        task_count = sum(task_blocks_closure(*row) for row in tasks)
        bindings = select(AaProgramBinding.program_id).where(AaProgramBinding.tenant_id == tenant_id,
            AaProgramBinding.is_deleted.is_(False), AaProgramBinding.status == 'ACTIVE',
            or_(AaProgramBinding.major_id.in_(major_ids), AaProgramBinding.class_id.in_(class_ids)))
        programs = db.scalars(select(AaProgram.id).where(AaProgram.tenant_id == tenant_id,
            AaProgram.is_deleted.is_(False), AaProgram.status.in_(_PROGRAM_USABLE),
            or_(AaProgram.major_id.in_(major_ids), AaProgram.id.in_(bindings)))).all()
        child_count = (sum(not row.is_deleted and row.status == 'ACTIVE' for row in majors) if kind == 'COLLEGE' else
                       sum(not row.is_deleted and row.status == 'ACTIVE' and row.class_status == 'NORMAL' for row in classes))
        refs = [_ref('ACTIVE_CHILD', '启用专业' if kind == 'COLLEGE' else '在读行政班', child_count,
                     '先核对下级组织的教学和学生安排，再处理停用或结班。'),
                _ref('PROGRAM', '生效培养方案', len(programs), '在培养方案业务中核对发布、启用及冻结版本的适用关系。')]
        if kind == 'COLLEGE':
            batches = db.execute(select(AaTeachingTaskBatch, AaTerm).outerjoin(AaTerm,
                and_(AaTerm.id == AaTeachingTaskBatch.term_id, AaTerm.tenant_id == tenant_id)).where(
                AaTeachingTaskBatch.tenant_id == tenant_id, AaTeachingTaskBatch.college_id == node.id,
                AaTeachingTaskBatch.is_deleted.is_(False),
                AaTeachingTaskBatch.status.notin_(['CANCELLED', 'ARCHIVED', 'COMPLETED']))).all()
            open_batches = sum(not term or term.is_deleted or term.status != 'ARCHIVED' for _, term in batches)
            refs.append(_ref('TEACHING_BATCH', '未归档教学任务批次', open_batches, '包括尚未生成任务的批次，需核对其学期教学安排。'))
        name = node.college_name if kind == 'COLLEGE' else node.major_name
    refs = [_ref('STUDENT', '在籍学生', student_count, '在学籍或班级调整业务中办理学生后续归属；本次核对不会修改学籍。'),
            _ref('TEACHING_TASK', '未归档教学任务', task_count, '处理相关教学任务，或按正式流程完成所属学期的教务归档。')] + refs
    historical = len(students) - student_count
    if historical:
        warnings.append(f'另有 {historical} 名已终结学籍学生的历史引用，仍需保留历史关系；不能据此直接删除组织。')
    if node.status != 'ACTIVE':
        warnings.append('该组织当前未启用；本次仅核对引用，不会改变其状态。')
    blockers = [f"{ref['label']}：{ref['refCount']}" for ref in refs if ref['blocked']]
    return {'targetType': kind, 'targetId': str(node.id), 'targetName': name,
            'version': int(node.version or 0), 'checkedAt': datetime.utcnow().isoformat() + 'Z',
            'refs': refs, 'blocked': bool(blockers), 'blockers': blockers, 'warnings': warnings,
            'historicalStudentCount': historical}
