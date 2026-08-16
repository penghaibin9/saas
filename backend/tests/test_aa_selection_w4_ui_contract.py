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

    # /teaching-tasks does not accept termId.  The UI first resolves the
    # current-term task batches, then intersects READY tasks by stable batchId;
    # backend same-term validation remains the authority on write.
    assert "academicAffairsApi.getTaskBatches({ termId" in source
    assert "academicAffairsApi.listAllTasks({ status: 'READY'" in source
    assert "allowedBatchIds.has(String(row.batchId))" in source

    assert "raw?.courseId" in source
    assert "raw?.courseCode" in source
    assert "raw?.courseName" in source
    assert "raw?.teacherName" in source
    assert "raw?.teachingClassName" in source
    assert "提交时不允许手工改写" in source

    assert "teachingTaskId: this.courseForm.teachingTaskId," in source
    assert "courseId: this.courseForm.courseId," in source
    assert "teachingTaskId: this.courseForm.teachingTaskId || undefined" not in source
    assert "请选择当前批次学期的 READY 教学任务" in source
