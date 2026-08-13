"""20K 13B 教务空间/考务对账。

主种子先生成考试课程与完整学生名单；本步骤按教室字典的 exam_seats 重新拆考场，
确保每个考场 planned_count <= 实际考试座位数，并保持每名学生恰好一个座位。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, func, select

from app.services.sandbox_school_master_seed import _bulk_insert


def reconcile_exam_rooms(db, tenant_id: int) -> dict:
    from app.models import (
        AaClassroom, AaExamCourse, AaExamInvigilator, AaExamRoom,
        AaExamRoomStudent, SchoolClass, StudentProfile, User,
    )

    # 主种子的临时单考场仅用于建立考试课程；正式验收前全部按真实考试容量重排。
    room_ids = list(db.scalars(select(AaExamRoom.id).where(
        AaExamRoom.tenant_id == tenant_id,
        AaExamRoom.is_deleted.is_(False),
    )))
    if room_ids:
        db.execute(delete(AaExamRoomStudent).where(
            AaExamRoomStudent.tenant_id == tenant_id,
            AaExamRoomStudent.exam_room_id.in_(room_ids),
        ))
        db.execute(delete(AaExamInvigilator).where(
            AaExamInvigilator.tenant_id == tenant_id,
            AaExamInvigilator.exam_room_id.in_(room_ids),
        ))
        db.execute(delete(AaExamRoom).where(
            AaExamRoom.tenant_id == tenant_id,
            AaExamRoom.id.in_(room_ids),
        ))
        db.flush()

    classrooms = list(db.execute(select(
        AaClassroom.id, AaClassroom.room_name, AaClassroom.exam_seats,
    ).where(
        AaClassroom.tenant_id == tenant_id,
        AaClassroom.status == "AVAILABLE",
        AaClassroom.is_deleted.is_(False),
        AaClassroom.exam_seats.is_not(None),
        AaClassroom.exam_seats >= 30,
    ).order_by(AaClassroom.id)).all())
    if len(classrooms) < 64:
        raise RuntimeError(f"可用标准考场不足: {len(classrooms)}")

    exam_courses = list(db.scalars(select(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.is_deleted.is_(False),
    ).order_by(AaExamCourse.id)).all())
    class_ids = sorted({int(x.class_id) for x in exam_courses if x.class_id})
    roster_by_class: dict[int, list] = defaultdict(list)
    for row in db.execute(select(
        StudentProfile.id, StudentProfile.student_no, StudentProfile.real_name, StudentProfile.class_id,
    ).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.class_id.in_(class_ids),
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.class_id, StudentProfile.student_no)).all():
        roster_by_class[int(row.class_id)].append(row)

    teachers = list(db.execute(select(User.login_name, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_t%"),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    if len(teachers) < 512:
        raise RuntimeError("监考教师池不足")

    room_rows = []
    room_plan: list[tuple[int, int, list, object]] = []
    classroom_cursor = 0
    for ec in exam_courses:
        roster = roster_by_class[int(ec.class_id)]
        cursor = 0
        room_seq = 1
        while cursor < len(roster):
            classroom = classrooms[classroom_cursor % len(classrooms)]
            classroom_cursor += 1
            capacity = int(classroom.exam_seats or 0)
            people = roster[cursor:cursor + capacity]
            room_rows.append({
                "tenant_id": tenant_id,
                "exam_course_id": int(ec.id),
                "room_seq": room_seq,
                "classroom_text": classroom.room_name,
                "capacity": capacity,
                "planned_count": len(people),
                "seat_mode": "SEQUENTIAL",
                "source": "AUTO",
                "status": "ACTIVE",
            })
            room_plan.append((int(ec.id), room_seq, people, classroom))
            cursor += len(people)
            room_seq += 1
    _bulk_insert(db, AaExamRoom, room_rows, chunk_size=1000)
    db.flush()

    room_by_key = {
        (int(exam_course_id), int(room_seq)): int(room_id)
        for room_id, exam_course_id, room_seq in db.execute(select(
            AaExamRoom.id, AaExamRoom.exam_course_id, AaExamRoom.room_seq,
        ).where(
            AaExamRoom.tenant_id == tenant_id,
            AaExamRoom.is_deleted.is_(False),
        )).all()
    }
    seat_rows = []
    invigilator_rows = []
    teacher_cursor = 0
    for ec_id, room_seq, people, _classroom in room_plan:
        room_id = room_by_key[(ec_id, room_seq)]
        for seat_no, stu in enumerate(people, 1):
            seat_rows.append({
                "tenant_id": tenant_id,
                "exam_room_id": room_id,
                "exam_course_id": ec_id,
                "student_id": int(stu.id),
                "student_no": stu.student_no,
                "student_name": stu.real_name,
                "seat_no": seat_no,
                "admission_no": f"{ec_id}{room_seq:02d}{seat_no:03d}",
                "attendance_status": "PRESENT",
            })
        # 每个拆分考场一个主监考；同一考试课程拆成两个考场时由不同教师负责。
        teacher = teachers[teacher_cursor % len(teachers)]
        teacher_cursor += 1
        invigilator_rows.append({
            "tenant_id": tenant_id,
            "exam_room_id": room_id,
            "teacher_key": teacher.login_name,
            "teacher_name": teacher.real_name,
            "role": "CHIEF",
            "confirm_status": "CONFIRMED",
        })
    _bulk_insert(db, AaExamRoomStudent, seat_rows, chunk_size=2000)
    _bulk_insert(db, AaExamInvigilator, invigilator_rows, chunk_size=1000)
    db.commit()

    over_capacity = int(db.scalar(select(func.count()).select_from(AaExamRoom).where(
        AaExamRoom.tenant_id == tenant_id,
        AaExamRoom.planned_count > AaExamRoom.capacity,
        AaExamRoom.is_deleted.is_(False),
    )) or 0)
    seat_count = int(db.scalar(select(func.count()).select_from(AaExamRoomStudent).where(
        AaExamRoomStudent.tenant_id == tenant_id,
        AaExamRoomStudent.is_deleted.is_(False),
    )) or 0)
    distinct_students_per_course = int(db.scalar(select(func.count()).select_from(
        select(AaExamRoomStudent.exam_course_id, AaExamRoomStudent.student_id)
        .where(
            AaExamRoomStudent.tenant_id == tenant_id,
            AaExamRoomStudent.is_deleted.is_(False),
        )
        .distinct()
        .subquery()
    )) or 0)
    if over_capacity:
        raise RuntimeError(f"存在 {over_capacity} 个超容量考场")
    if distinct_students_per_course != seat_count:
        raise RuntimeError(
            f"考试座位重复: seats={seat_count}, uniqueCourseStudents={distinct_students_per_course}"
        )
    return {
        "examCourses": len(exam_courses),
        "examRooms": len(room_rows),
        "examSeats": seat_count,
        "invigilators": len(invigilator_rows),
        "roomsOverCapacity": over_capacity,
        "passed": True,
    }
