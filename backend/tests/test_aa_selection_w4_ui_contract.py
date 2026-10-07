"""B-W4 · management PC SelectionCourse supply must be TeachingTask-first."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/modules/academicAffairs/views/AaSelectionConsoleView.vue"


def test_w4_selection_console_is_teaching_task_first():
    source = VIEW.read_text(encoding="utf-8")

    assert "AppCoursePicker" not in source
    assert 'label="教学任务" required' in source
    assert ':remote-search="searchSelectionTasks"' in source
    assert '@change="onSelectionTaskChange"' in source

    # The paged task endpoint now filters the active term on the server.
    # Keep both the term and READY-state constraints, including stale-read guard.
    assert "const termId = this.current?.termId" in source
    assert "academicAffairsApi.listAllTasks({\n        termId," in source
    assert "status: 'READY'" in source
    assert "if (!this.isCurrent(context)) return []" in source

    assert "raw?.courseId" in source
    assert "raw?.courseCode" in source
    assert "raw?.courseName" in source
    assert "raw?.teacherName" in source
    assert "raw?.teachingClassName" in source
    assert "提交时不允许手工改写" in source

    assert "teachingTaskId: this.courseForm.teachingTaskId," in source
    assert "courseId: this.courseForm.courseId," in source
    assert "teachingTaskId: this.courseForm.teachingTaskId || undefined" not in source
    assert "请选择当前批次学期的已就绪教学任务" in source
