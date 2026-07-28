from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_portal_keeps_refresh_files_internship_and_graduation_cleanup():
    source = read("student-portal/src/services/request.js")
    for marker in (
        "refreshOnce",
        "X-Internship-Batch-Id",
        "uploadFile",
        "downloadFile",
        "GD_TEMP_FILES_KEY",
        "cleanupStaleGraduationTemps",
        "rememberTempFile",
    ):
        assert marker in source
    assert "/auth/mock-login" not in source


def test_miniapp_keeps_refresh_files_internship_and_graduation_paging():
    source = read("miniapp/src/services/request.js")
    for marker in (
        "_refreshOnce",
        "X-Internship-Batch-Id",
        "realUpload",
        "realDownload",
        "GD_TEACHER_BATCH_KEY",
        "withTeacherGraduationContext",
        "collectTeacherGraduationPages",
    ):
        assert marker in source
    assert "业务错误透出" in source or "e.biz" in source
