"""教务最终facade映射与当前模型事实基线回归。"""


def test_public_service_aliases_point_to_final_layers():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_archive_service.__name__.endswith(
        "academic_affairs_archive_textbook_facade"
    )
    assert services.academic_affairs_evaluation_service.__name__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
    assert services.academic_affairs_makeup_service.__name__.endswith(
        "academic_affairs_makeup_term_facade"
    )
    assert services.academic_affairs_textbook_service.__name__.endswith(
        "academic_affairs_textbook_roster_facade"
    )
    assert services.academic_affairs_textbook_service.generate_distribution.__module__.endswith(
        "academic_affairs_textbook_roster_facade"
    )
    assert services.academic_affairs_exam_service.__name__.endswith(
        "academic_affairs_exam_term_facade"
    )
    assert services.academic_affairs_exam_service.create_batch.__module__.endswith(
        "academic_affairs_exam_term_facade"
    )
    assert services.academic_affairs_exam_service.assign_seats.__module__.endswith(
        "academic_affairs_exam_facade"
    )
    assert services.academic_affairs_grade_service.__name__.endswith(
        "academic_affairs_grade_term_facade"
    )
    assert services.academic_affairs_grade_service.submit_task.__module__.endswith(
        "academic_affairs_grade_term_facade"
    )
    assert services.academic_affairs_grade_service.grade_import_confirm.__module__.endswith(
        "academic_affairs_grade_term_facade"
    )
    assert services.academic_affairs_grade_service.roster.__module__.endswith(
        "academic_affairs_grade_roster_facade"
    )
    assert services.academic_affairs_selection_service.create_batch.__module__.endswith(
        "academic_affairs_selection_facade"
    )
    assert services.academic_affairs_attendance_service.create_session.__module__.endswith(
        "academic_affairs_attendance_facade"
    )


def test_current_model_fields_used_by_facades_exist():
    from app.models import (
        AaAttendanceSession,
        AaExamIncident,
        AaGradeRecord,
        AaGradeTask,
        AaSchedulePublish,
        AaSelectionCourse,
        AaSelectionRecord,
        AaTeachingTask,
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        SchoolClass,
    )

    required = {
        AaAttendanceSession: {"class_id", "course_name", "term_code", "roster_json", "status"},
        AaExamIncident: {"exam_course_id", "incident_type", "discipline_case_ref", "risk_alert_sent", "status"},
        AaGradeTask: {"teaching_task_id", "term_id", "term_code", "course_id", "class_id", "status"},
        AaGradeRecord: {"task_id", "student_id", "exception_flag", "total_score", "status"},
        AaSchedulePublish: {"batch_id", "term_id", "action", "note"},
        AaSelectionCourse: {"batch_id", "teaching_task_id", "selected_count", "status"},
        AaSelectionRecord: {"batch_id", "selection_course_id", "student_id", "status"},
        AaTeachingTask: {"batch_id", "course_id", "class_id", "expected_students", "merge_snapshot_json", "status"},
        AaTextbookOrderBatch: {"term_id", "status"},
        AaTextbookDistributionBatch: {"order_batch_id", "status"},
        AaTextbookDistributionRecord: {"batch_id", "status"},
        AaTextbookFeeLedger: {"distribution_record_id", "status", "paid_amount"},
        SchoolClass: {"class_name", "class_status", "status"},
    }
    # CommonMixin provides status only where the concrete model declares it; inspect mapper attrs rather than __dict__.
    for model, fields in required.items():
        attrs = set(model.__mapper__.attrs.keys())
        # AaGradeRecord has no business status column; its row state is carried by task + exception/pass flags.
        expected = fields - ({"status"} if model is AaGradeRecord else set())
        assert expected <= attrs, f"{model.__name__} missing {sorted(expected - attrs)}"


def test_grade_record_does_not_invent_row_level_workflow_status():
    from app.models import AaGradeRecord

    assert "status" not in set(AaGradeRecord.__mapper__.attrs.keys())
    assert {"exception_flag", "pass_status", "source"} <= set(AaGradeRecord.__mapper__.attrs.keys())
