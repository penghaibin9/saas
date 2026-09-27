def test_shared_model_kernel_imports():
    from app import models
    for name in ["Tenant","User","Role","College","Major","SchoolClass","StudentProfile","StudentAccountLink","EmpCompany","InternshipBatch","InternshipRecord","InternshipPosition","FileObject","FileAsset","FileVersion","FileBinding"]:
        assert getattr(models,name) is not None

def test_scope_defaults_fail_closed():
    from app.services.mobile_teacher_service import resolve_teacher_scope,scope_match_row
    scope=resolve_teacher_scope({"userType":"UNKNOWN"})
    assert scope["mode"]=="SCOPED"
    assert not scope_match_row(scope,student_no="S001")


def test_representative_internship_services_import():
    from app.modules.internship.services import internship_service
    from app.modules.internship.services import internship_student_service
    from app.modules.internship.services import internship_enterprise_service
    from app.modules.internship.services import internship_application_service
    from app.modules.internship.services import internship_archive_service
    from app.modules.internship.services import internship_stats_service

    assert internship_service is not None
    assert internship_student_service is not None
    assert internship_enterprise_service is not None
    assert internship_application_service is not None
    assert internship_archive_service is not None
    assert internship_stats_service is not None
