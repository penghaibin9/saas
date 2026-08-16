from pathlib import Path

path = Path("backend/tests/test_mobile_attendance.py")
text = path.read_text(encoding="utf-8")

old = '''    from app.models import (\n        AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion,\n        AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch, AaTerm,\n        StudentProfile,\n    )\n'''
new = '''    from app.models import (\n        AaScheduleBatch, AaScheduleItem, AaTeachingClass, AaTeachingClassMember,\n        AaTeachingClassRosterVersion, AaTeachingClassTeacher, AaTeachingTask,\n        AaTeachingTaskBatch, AaTerm, StudentProfile,\n    )\n    from app.models.academic_affairs import AaScheduleScopeHead\n'''
if text.count(old) != 1:
    raise SystemExit(f"helper import anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''            term_name="2026-2027学年第一学期",\n            start_date=datetime(2026, 1, 1), end_date=datetime(2026, 12, 31),\n            teaching_weeks=20, is_current=True, status="PUBLISHED")\n'''
new = '''            term_name="2026-2027学年第一学期",\n            start_date=datetime(2026, 7, 13), end_date=datetime(2026, 11, 15),\n            teaching_weeks=18, is_current=True, status="PUBLISHED")\n'''
if text.count(old) != 1:
    raise SystemExit(f"term calendar anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''        teaching_class.current_roster_version_id = version.id\n        teaching_class.current_roster_version_no = 1\n        teaching_class.roster_status = "LOCKED"\n        task.expected_students = len(student_ids)\n        db.commit()\n        return task.id\n'''
new = '''        teaching_class.current_roster_version_id = version.id\n        teaching_class.current_roster_version_no = 1\n        teaching_class.roster_status = "LOCKED"\n        task.expected_students = len(student_ids)\n\n        schedule_batch = AaScheduleBatch(\n            tenant_id=tenant_id, term_id=term.id,\n            batch_name="考勤测试正式课表", status="PUBLISHED")\n        db.add(schedule_batch); db.flush()\n        tue = AaScheduleItem(\n            tenant_id=tenant_id, batch_id=schedule_batch.id, task_id=task.id,\n            course_id=task.course_id, course_name=task.course_name,\n            teacher_key=task.teacher_key, teacher_name=task.teacher_name,\n            class_id=class_id, weekday=2, slot_no=2,\n            start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE")\n        wed = AaScheduleItem(\n            tenant_id=tenant_id, batch_id=schedule_batch.id, task_id=task.id,\n            course_id=task.course_id, course_name=task.course_name,\n            teacher_key=task.teacher_key, teacher_name=task.teacher_name,\n            class_id=class_id, weekday=3, slot_no=3,\n            start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE")\n        db.add_all([tue, wed]); db.flush()\n        db.add(AaScheduleScopeHead(\n            tenant_id=tenant_id, term_id=term.id, scope_type="SCHOOL", scope_id=0,\n            active_batch_id=schedule_batch.id, version=1, published_at=datetime.utcnow()))\n        db.commit()\n        return {\n            "taskId": task.id,\n            "occurrences": {\n                "2026-07-14": {"slotNo": 2, "scheduleItemId": str(tue.id)},\n                "2026-07-15": {"slotNo": 3, "scheduleItemId": str(wed.id)},\n            },\n        }\n'''
if text.count(old) != 1:
    raise SystemExit(f"formal schedule seed anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''    task_id = _seed_teaching_task(cid, "周老师")\n    hdr = _teacher_token("周老师")\n    r = client.post(f"{BASE}/sessions", headers=hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "高等数学", "sessionDate": "2026-07-15"}).json()\n'''
new = '''    seeded = _seed_teaching_task(cid, "周老师")\n    task_id = seeded["taskId"]\n    occurrence = seeded["occurrences"]["2026-07-15"]\n    hdr = _teacher_token("周老师")\n    r = client.post(f"{BASE}/sessions", headers=hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "高等数学", "sessionDate": "2026-07-15",\n                          "slotNo": occurrence["slotNo"],\n                          "scheduleItemId": occurrence["scheduleItemId"]}).json()\n'''
if text.count(old) != 1:
    raise SystemExit(f"full-flow occurrence anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''    task_id = _seed_teaching_task(cid, "张老师")\n    owner_hdr = _teacher_token("张老师")\n    r = client.post(f"{BASE}/sessions", headers=owner_hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "英语", "sessionDate": "2026-07-15"}).json()\n'''
new = '''    seeded = _seed_teaching_task(cid, "张老师")\n    task_id = seeded["taskId"]\n    occurrence = seeded["occurrences"]["2026-07-15"]\n    owner_hdr = _teacher_token("张老师")\n    r = client.post(f"{BASE}/sessions", headers=owner_hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "英语", "sessionDate": "2026-07-15",\n                          "slotNo": occurrence["slotNo"],\n                          "scheduleItemId": occurrence["scheduleItemId"]}).json()\n'''
if text.count(old) != 1:
    raise SystemExit(f"owner-flow occurrence anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''    task_id = _seed_teaching_task(cid, "孙老师")\n    hdr = _teacher_token("孙老师")\n    PC = "/api/v1/academic-affairs/attendance"\n    # 场次1：常规类别（不传=常规），1 人旷课\n    s1_payload = client.post(f"{BASE}/sessions", headers=hdr, json={\n        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()\n'''
new = '''    seeded = _seed_teaching_task(cid, "孙老师")\n    task_id = seeded["taskId"]\n    tue = seeded["occurrences"]["2026-07-14"]\n    wed = seeded["occurrences"]["2026-07-15"]\n    hdr = _teacher_token("孙老师")\n    PC = "/api/v1/academic-affairs/attendance"\n    # 场次1：常规类别（不传=常规），1 人旷课\n    s1_payload = client.post(f"{BASE}/sessions", headers=hdr, json={\n        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-14",\n        "slotNo": tue["slotNo"], "scheduleItemId": tue["scheduleItemId"]}).json()\n'''
if text.count(old) != 1:
    raise SystemExit(f"stats-flow first occurrence anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''    s2 = client.post(f"{BASE}/sessions", headers=hdr, json={\n        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-15",\n        "sessionType": "实训"}).json()["data"]\n'''
new = '''    s2 = client.post(f"{BASE}/sessions", headers=hdr, json={\n        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-15",\n        "slotNo": wed["slotNo"], "scheduleItemId": wed["scheduleItemId"],\n        "sessionType": "实训"}).json()["data"]\n'''
if text.count(old) != 1:
    raise SystemExit(f"stats-flow second occurrence anchor count={text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
