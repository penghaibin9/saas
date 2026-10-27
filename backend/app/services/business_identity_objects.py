"""Read-only object labels and existing domain destinations for relationship records."""
from sqlalchemy import select


def describe_objects(db, tenant_id, references):
    from app.models import (SchoolClass, StudentProfile, AaTeachingClass, AaTeachingTask,
        AaTeachingTaskBatch, GraduationStudent, GraduationReview, GraduationDefenseGroup,
        GraduationBatch, InternshipRecord, InternshipBatch)
    kinds = {'class': SchoolClass, 'teachingClass': AaTeachingClass, 'teachingTask': AaTeachingTask,
             'gdStudent': GraduationStudent, 'gdReview': GraduationReview,
             'defenseGroup': GraduationDefenseGroup, 'internship': InternshipRecord}
    grouped = {}
    for ref in references:
        kind, _, identifier = ref.partition(':')
        if kind in kinds and identifier.isdigit():
            grouped.setdefault(kind, set()).add(int(identifier))
    def read(model, identifiers):
        if not identifiers:
            return {}
        return {row.id: row for row in db.scalars(select(model).where(model.tenant_id == tenant_id,
            model.is_deleted.is_(False), model.id.in_(identifiers))).all()}
    records = {kind: read(kinds[kind], identifiers) for kind, identifiers in grouped.items()}
    tasks = dict(records.get('teachingTask', {}))
    tasks.update(read(AaTeachingTask, {r.teaching_task_id for r in records.get('teachingClass', {}).values()}))
    students = read(StudentProfile, {r.student_id for r in records.get('internship', {}).values()})
    gd_students = dict(records.get('gdStudent', {}))
    gd_students.update(read(GraduationStudent, {r.gd_student_id for r in records.get('gdReview', {}).values()}))
    academic_batches = read(AaTeachingTaskBatch, {r.batch_id for r in tasks.values()})
    gd_batches = read(GraduationBatch, {r.batch_id for r in gd_students.values() if r.batch_id})
    intern_batches = read(InternshipBatch, {r.batch_id for r in records.get('internship', {}).values() if r.batch_id})
    def masked(value):
        text = str(value or '')
        return text[:3] + '****' + text[-2:] if len(text) > 4 else text
    result = {}
    for ref in references:
        kind, _, identifier = ref.partition(':')
        row = records.get(kind, {}).get(int(identifier)) if identifier.isdigit() else None
        item = {'reference': ref, 'label': '对象已失效或不在本校', 'available': False, 'route': None,
                'batchId': '', 'batchName': '', 'state': 'MISSING'}
        if row is not None:
            item.update(available=True, state='RECORDED')
            if kind == 'class':
                item.update(label=row.class_name, route={'path': f'/admin/campus-service/classes/{row.id}'})
                item['state'] = 'ACTIVE' if row.status == 'ACTIVE' else 'INACTIVE'
            elif kind in ('teachingClass', 'teachingTask'):
                task = tasks.get(row.teaching_task_id) if kind == 'teachingClass' else row
                if row.status in ('ARCHIVED', 'MERGED'):
                    item['state'] = 'INACTIVE'
                item['label'] = getattr(row, 'class_name', None) or getattr(row, 'teaching_class_name', None) or '教学任务'
                if task and task.batch_id in academic_batches:
                    batch = academic_batches[task.batch_id]
                    item.update(batchId=str(batch.id), batchName=batch.batch_name,
                        route={'path': f'/admin/academic-affairs/teaching-tasks/{batch.id}', 'query': {'teachingTaskId': str(task.id)}})
            elif kind in ('gdStudent', 'gdReview'):
                student = gd_students.get(row.gd_student_id) if kind == 'gdReview' else row
                if student:
                    batch = gd_batches.get(student.batch_id)
                    item.update(label='毕设学生 ' + (masked(student.student_no) or '学号待核对'),
                        batchId=str(student.batch_id or ''), batchName=batch.batch_name if batch else '批次待核对',
                        route={'path': f'/admin/graduation/students/{student.id}', 'query': {'batchId': str(student.batch_id)}} if batch else None)
                    item['state'] = 'ACTIVE' if student.record_status == 'ACTIVE' else 'INACTIVE'
                    if batch and batch.status in ('CLOSED', 'ARCHIVED', 'VOIDED'):
                        item['state'] = 'INACTIVE'
            elif kind == 'internship':
                student = students.get(row.student_id); batch = intern_batches.get(row.batch_id)
                item.update(label='实习学生 ' + (masked(student.student_no) if student else '学号待核对'),
                    batchId=str(row.batch_id or ''), batchName=batch.batch_name if batch else '批次待核对',
                    route={'path': f'/admin/internship/students/{row.id}', 'query': {'batchId': str(row.batch_id)}} if batch else None)
                item['state'] = 'INACTIVE' if row.status == 'ARCHIVED' else 'ACTIVE'
                if batch and batch.status in ('CLOSED', 'ARCHIVED', 'VOIDED'):
                    item['state'] = 'INACTIVE'
            elif kind == 'defenseGroup':
                item['label'] = getattr(row, 'group_name', None) or '毕设答辩分组'
        result[ref] = item
    return result
