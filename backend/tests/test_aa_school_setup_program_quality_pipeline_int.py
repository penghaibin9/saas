"""INT proof that Program credit-quality failure short-circuits later reads."""
from __future__ import annotations

from decimal import Decimal


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline
    return pipeline


def _rows():
    key = "SERIES:SER-A:v1"
    return [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": key,
            "definitionKey": key,
            "payload": {
                "programSeriesKey": "SER-A",
                "programVersion": 1,
                "programName": "软件技术培养方案",
                "majorId": 10,
                "gradeYear": "2026",
                "totalCredits": Decimal("5"),
                "educationYearsAssertion": 3,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": key,
            "definitionKey": f"{key}|COURSE|CS101@v1",
            "payload": {
                "programKey": key,
                "courseKey": "CS101@v1",
                "formationMode": "ADMIN_FIXED",
                "module": "专业核心",
                "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": key,
            "definitionKey": f"{key}|CREDIT|专业核心",
            "payload": {
                "programKey": key,
                "module": "专业核心",
                "creditTarget": Decimal("5"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": key,
            "definitionKey": f"{key}|GRADUATION|ABILITY|完成项目",
            "payload": {
                "programKey": key,
                "category": "ABILITY",
                "content": "完成项目",
                "sortOrder": 0,
            },
        },
    ]


def test_quality_failure_stops_before_definition_binding_and_status_reads():
    calls = []

    def scope():
        calls.append(("scope", ()))
        return None

    def majors(keys):
        calls.append(("major", tuple(keys)))
        return [{"majorId": 10, "educationYears": 3, "status": "ACTIVE"}]

    def courses(keys):
        calls.append(("course", tuple(keys)))
        return [{
            "courseId": 101,
            "courseCode": "CS101",
            "version": 1,
            "status": "ENABLED",
            "credit": Decimal("3"),
            "payload": {},
        }]

    def programs(keys):
        calls.append(("program", tuple(keys)))
        return []

    def forbidden(name):
        def _loader(keys):
            calls.append((name, tuple(keys)))
            raise AssertionError(f"QUALITY failure must not call {name}")
        return _loader

    result = _pipeline().run_program_import_preflight(
        _rows(),
        phase="DEFINITION",
        load_allowed_major_ids=scope,
        load_major_snapshots=majors,
        load_class_snapshots=forbidden("class"),
        load_course_snapshots=courses,
        load_program_snapshots=programs,
        load_existing_definition_rows=forbidden("definitions"),
        load_program_status_by_id=forbidden("status"),
        load_active_binding_snapshots=forbidden("active_binding"),
    )

    assert result["stage"] == "QUALITY"
    assert result["programPreflightSafe"] is False
    assert result["quality"]["definitionQualitySafe"] is False
    assert result["definition"] == {}
    assert result["binding"] == {}
    assert result["errors"] == [{
        "row": 2,
        "logicalGroup": "MAIN",
        "programKey": "SERIES:SER-A:v1",
        "businessCode": "PROGRAM_ACTUAL_CREDIT_INSUFFICIENT",
        "message": "课程与实践学分合计未达到培养方案毕业总学分，禁止写入明知无法提交的方案定义",
        "evidence": {
            "courseCreditSum": "3",
            "practiceCreditSum": "0",
            "actualCreditSum": "3",
            "totalCredits": "5",
        },
        "howToResolve": "补齐 COURSE/PRACTICE 定义或修正 MAIN.totalCredits；课程学分以 exact Course version 为准",
    }, {
        "row": 2,
        "logicalGroup": "CREDIT_REQUIREMENT",
        "programKey": "SERIES:SER-A:v1",
        "businessCode": "PROGRAM_MODULE_CREDIT_INSUFFICIENT",
        "message": "课程模块实际学分未达到配置的模块目标学分",
        "evidence": {
            "module": "专业核心",
            "actualCredit": "3",
            "creditTarget": "5",
        },
        "howToResolve": "补齐该模块 COURSE 定义或调整 CREDIT_REQUIREMENT 目标；PRACTICE 学分不会被静默计入课程模块",
    }]
    assert calls == [
        ("scope", ()),
        ("major", (10,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
    ]
