"""Shared current references for administrative class lifecycle checks.

The caller locks the class rows first and owns the transaction. Historical
students remain linked; only nonterminal students and open teaching tasks block
closing a class. Deletion can impose the stricter historical-reference rule.
"""
from sqlalchemy import and_, select

EXITED_STUDENT_STATUSES = frozenset({'GRADUATED', 'WITHDRAWN', 'TRANSFER_SCHOOL', 'COMPLETED', 'INCOMPLETE', 'MERGED', 'RECYCLED'})


def read_class_references(db, tenant_id, class_ids, *, lock=True):
    from app.models import StudentProfile, AaTeachingTask

    ids = sorted(set(class_ids))
    students_query = (select(StudentProfile).where(StudentProfile.tenant_id == tenant_id,
        StudentProfile.class_id.in_(ids), StudentProfile.is_deleted.is_(False))
        .order_by(StudentProfile.id).execution_options(populate_existing=True))
    students = db.scalars(students_query.with_for_update() if lock else students_query).all()
    tasks = read_teaching_references(db, tenant_id, AaTeachingTask.class_id.in_(ids), lock=lock)
    student_counts, task_counts = {}, {}
    for student in students:
        if student.student_status not in EXITED_STUDENT_STATUSES:
            student_counts[student.class_id] = student_counts.get(student.class_id, 0) + 1
    for task, batch, term in tasks:
        if task_blocks_closure(task, batch, term):
            task_counts[task.class_id] = task_counts.get(task.class_id, 0) + 1
    return students, tasks, student_counts, task_counts


def task_blocks_closure(task, batch, term):
    return task.status not in {'MERGED', 'CANCELLED', 'ARCHIVED', 'COMPLETED'} and (
        not batch or batch.is_deleted or not term or term.is_deleted or term.status != 'ARCHIVED')


def read_teaching_references(db, tenant_id, condition, *, lock=True):
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm
    query = select(AaTeachingTask, AaTeachingTaskBatch, AaTerm).outerjoin(
        AaTeachingTaskBatch, and_(AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
                                 AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id)).outerjoin(
        AaTerm, and_(AaTerm.id == AaTeachingTaskBatch.term_id, AaTerm.tenant_id == AaTeachingTask.tenant_id)).where(
        AaTeachingTask.tenant_id == tenant_id, AaTeachingTask.is_deleted.is_(False), condition,
        AaTeachingTask.status.notin_(['MERGED', 'CANCELLED', 'ARCHIVED', 'COMPLETED'])).order_by(
        AaTeachingTask.id).execution_options(populate_existing=True)
    return db.execute(query.with_for_update() if lock else query).all()


def closing_blockers(student_count, task_count):
    blockers = []
    if student_count:
        blockers.append(f'仍有 {student_count} 名在籍学生，请先处理转班或离校学籍手续')
    if task_count:
        blockers.append(f'仍有 {task_count} 条未归档教学任务，请先处理教学任务或完成所属学期的教务归档')
    return blockers


def reference_snapshot(students, tasks):
    return {
        'students': [[row.id, row.class_id, row.student_status, row.version] for row in students],
        'tasks': [[task.id, task.class_id, task.version, task.status, task.batch_id,
                   batch.version if batch else None, batch.is_deleted if batch else None,
                   batch.term_id if batch else None, term.status if term else None,
                   term.version if term else None, term.is_deleted if term else None] for task, batch, term in tasks],
    }
