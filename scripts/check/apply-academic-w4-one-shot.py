from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"W4 patch anchor missing: {path}\n--- anchor ---\n{old[:500]}")
    if text.count(old) != 1:
        raise SystemExit(f"W4 patch anchor not unique: {path} count={text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Backend: make schedule PARTIAL a real server-authoritative capability.
# ---------------------------------------------------------------------------
patch(
    "backend/app/modules/academic_affairs/services/academic_file_exchange_service.py",
    '''def _detail(row, errors: list[dict] | None = None, rows: list[dict] | None = None) -> dict:\n    result = jobs._import_row(row)\n    snapshot = dict(row.source_snapshot_json or {})\n    result["preview"] = {\n        **dict(snapshot.get("preview") or {}),\n        "errors": errors or [],\n        "rows": _redacted_rows(rows or []),\n    }\n    return result\n''',
    '''def _detail(row, errors: list[dict] | None = None, rows: list[dict] | None = None) -> dict:\n    result = jobs._import_row(row)\n    snapshot = dict(row.source_snapshot_json or {})\n    context = dict(snapshot.get("context") or {})\n    import_mode = str(context.get("importMode") or "ATOMIC").strip().upper()\n    partial_schedule = (\n        row.import_type == ACADEMIC_SCHEDULE_IMPORT\n        and import_mode == "PARTIAL"\n        and int(row.valid_rows or 0) > 0\n        and row.status in {"VALIDATED", "VALIDATION_FAILED"}\n    )\n    result["preview"] = {\n        **dict(snapshot.get("preview") or {}),\n        "errors": errors or [],\n        "rows": _redacted_rows(rows or []),\n    }\n    result["importMode"] = import_mode if row.import_type == ACADEMIC_SCHEDULE_IMPORT else None\n    result["canConfirm"] = bool(\n        (row.status == "VALIDATED" and int(row.invalid_rows or 0) == 0 and int(row.valid_rows or 0) > 0)\n        or partial_schedule\n    )\n    return result\n''',
)

patch(
    "backend/app/modules/academic_affairs/services/academic_file_exchange_service.py",
    '''    digest = _row_digest(rows)\n    if snapshot.get("rowDigest") and snapshot["rowDigest"] != digest:\n        raise AppException("DATA_CONFLICT", "导入文件解析结果已变化，请重新上传预检")\n    _total, _valid, invalid = _preview_counts(rows, preview)\n    if invalid:\n        raise AppException("VALIDATION_ERROR", "确认前重新预检发现错误，请重新上传修正后的文件")\n\n    if import_type == ACADEMIC_ROSTER_IMPORT:\n''',
    '''    digest = _row_digest(rows)\n    if snapshot.get("rowDigest") and snapshot["rowDigest"] != digest:\n        raise AppException("DATA_CONFLICT", "导入文件解析结果已变化，请重新上传预检")\n    _total, _valid, invalid = _preview_counts(rows, preview)\n    partial_schedule = (\n        import_type == ACADEMIC_SCHEDULE_IMPORT\n        and str(context.get("importMode") or "ATOMIC").strip().upper() == "PARTIAL"\n        and int(_valid or 0) > 0\n    )\n    if invalid and not partial_schedule:\n        raise AppException("VALIDATION_ERROR", "确认前重新预检发现错误，请重新上传修正后的文件")\n\n    if import_type == ACADEMIC_ROSTER_IMPORT:\n''',
)

patch(
    "backend/app/modules/academic_affairs/services/academic_file_exchange_service.py",
    '''    if not isinstance(result, dict):\n        result = {"result": result}\n    result = dict(result)\n    result.setdefault("confirmedRows", len(rows))\n    return result\n''',
    '''    if not isinstance(result, dict):\n        result = {"result": result}\n    result = dict(result)\n    if import_type == ACADEMIC_SCHEDULE_IMPORT:\n        result.setdefault("confirmedRows", int(result.get("imported") or 0))\n    else:\n        result.setdefault("confirmedRows", len(rows))\n    return result\n''',
)

patch(
    "backend/app/services/data_exchange_confirm_legacy.py",
    '''def _begin_adapter_confirm(job_id: str, expected_version: int, user: dict) -> tuple[str, str, str]:\n''',
    '''def _allows_partial_schedule(row) -> bool:\n    if row.import_type != "ACADEMIC_SCHEDULE":\n        return False\n    snapshot = dict(row.source_snapshot_json or {})\n    context = dict(snapshot.get("context") or {})\n    return (\n        str(context.get("importMode") or "ATOMIC").strip().upper() == "PARTIAL"\n        and int(row.valid_rows or 0) > 0\n        and row.status in {"VALIDATED", "VALIDATION_FAILED"}\n    )\n\n\ndef _begin_adapter_confirm(job_id: str, expected_version: int, user: dict) -> tuple[str, str, str]:\n''',
)

patch(
    "backend/app/services/data_exchange_confirm_legacy.py",
    '''        if row.invalid_rows or row.status == "VALIDATION_FAILED":\n            raise AppException("VALIDATION_ERROR", "该任务存在预检错误，禁止确认导入")\n        if row.status == "CONFIRMING" and row.lease_started_at \\\n                and row.lease_started_at > jobs._now() - timedelta(seconds=jobs.LEASE_STALE_SECONDS):\n            raise AppException("DATA_CONFLICT", "该任务正在另一服务实例确认，请稍后刷新")\n        if row.status not in {"VALIDATED", "CONFIRMING"}:\n            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许确认")\n''',
    '''        partial_schedule = _allows_partial_schedule(row)\n        if (row.invalid_rows or row.status == "VALIDATION_FAILED") and not partial_schedule:\n            raise AppException("VALIDATION_ERROR", "该任务存在预检错误，禁止确认导入")\n        if row.status == "CONFIRMING" and row.lease_started_at \\\n                and row.lease_started_at > jobs._now() - timedelta(seconds=jobs.LEASE_STALE_SECONDS):\n            raise AppException("DATA_CONFLICT", "该任务正在另一服务实例确认，请稍后刷新")\n        if row.status not in {"VALIDATED", "CONFIRMING"} and not partial_schedule:\n            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许确认")\n''',
)

patch(
    "backend/app/services/data_exchange_confirm_legacy.py",
    '''        if row.lease_token == lease:\n            row.status = "VALIDATED"\n            row.lease_token = None\n''',
    '''        if row.lease_token == lease:\n            row.status = "VALIDATION_FAILED" if int(row.invalid_rows or 0) > 0 else "VALIDATED"\n            row.lease_token = None\n''',
)

# ---------------------------------------------------------------------------
# Course: explicit template + authoritative batch import on existing page.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''    <template #actions>\n      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</AppButton>\n    </template>\n''',
    '''    <template #actions>\n      <AppButton @click="downloadCourseTemplate">下载导入模板</AppButton>\n      <AppButton @click="importVisible = true">批量导入</AppButton>\n      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</AppButton>\n    </template>\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''    </div>\n  </ModulePageShell>\n</template>\n''',
    '''    </div>\n\n    <AaAuthoritativeImportDrawer\n      v-model:visible="importVisible"\n      title="课程库权威 XLSX 导入"\n      template-name="课程库权威导入模板.xlsx"\n      :preview-fields="['courseCode', 'courseName', 'version', 'credit', 'category', 'nature']"\n      :download-template-fn="academicFileExchangeApi.downloadCourseCatalogTemplate"\n      :upload-fn="academicFileExchangeApi.uploadCourseCatalogImport"\n      @imported="onCourseImported"\n    />\n  </ModulePageShell>\n</template>\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\n''',
    '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'\nimport AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'\nimport { toast } from '@/utils/toast'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AdvancedFilter },\n''',
    '''  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AdvancedFilter, AaAuthoritativeImportDrawer },\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''      COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS,\n      loading: true, error: '', rows: [],\n''',
    '''      COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, academicFileExchangeApi,\n      loading: true, error: '', rows: [], importVisible: false,\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaCourseListView.vue",
    '''    reset() { this.filters = { keyword: '', category: '', nature: '', status: '' }; this.search() },\n    async load() {\n''',
    '''    reset() { this.filters = { keyword: '', category: '', nature: '', status: '' }; this.search() },\n    async downloadCourseTemplate() {\n      const res = await academicFileExchangeApi.downloadCourseCatalogTemplate()\n      if (res.code !== 0) { toast.error(res.message || '课程导入模板下载失败'); return }\n      const url = URL.createObjectURL(res.data)\n      const a = document.createElement('a'); a.href = url; a.download = '课程库权威导入模板.xlsx'; a.click(); URL.revokeObjectURL(url)\n    },\n    async onCourseImported() { toast.success('课程库权威导入已完成'); this.importVisible = false; await this.load() },\n    async load() {\n''',
)

# ---------------------------------------------------------------------------
# Program: explicit user-selected DEFINITION / BINDING phase.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''    <template #actions>\n      <AppButton @click="$router.push('/admin/academic-affairs/programs/opening-plan')">开课差异</AppButton>\n      <AppButton variant="primary" @click="showCreate = !showCreate">＋ 新建方案</AppButton>\n    </template>\n\n    <div class="mp-stack">\n''',
    '''    <template #actions>\n      <AppButton @click="importChooserVisible = !importChooserVisible">Excel导入</AppButton>\n      <AppButton @click="$router.push('/admin/academic-affairs/programs/opening-plan')">开课差异</AppButton>\n      <AppButton variant="primary" @click="showCreate = !showCreate">＋ 新建方案</AppButton>\n    </template>\n\n    <div class="mp-stack">\n      <AppSectionCard v-if="importChooserVisible" title="培养方案 Excel 导入阶段" subtitle="同一六工作表模板，阶段由操作者明确选择；浏览器不推断写入顺序">\n        <AppInlineAlert type="info" description="先导入方案定义并确认，再按实施进度导入适用范围绑定；两个阶段分别形成独立 ImportJob 与审计证据。" />\n        <div class="aa-actions">\n          <AppButton variant="primary" @click="openProgramImport('DEFINITION')">1. 方案定义</AppButton>\n          <AppButton @click="openProgramImport('BINDING')">2. 适用范围绑定</AppButton>\n          <AppButton variant="ghost" @click="downloadProgramTemplate">下载六工作表模板</AppButton>\n        </div>\n      </AppSectionCard>\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''    </div>\n  </ModulePageShell>\n</template>\n''',
    '''    </div>\n\n    <AaAuthoritativeImportDrawer\n      v-model:visible="importVisible"\n      title="培养方案六工作表权威导入"\n      template-name="培养方案六工作表权威导入模板.xlsx"\n      :phase-label="programImportPhase === 'DEFINITION' ? '1. 方案定义（DEFINITION）' : '2. 适用范围绑定（BINDING）'"\n      :preview-fields="['sheetName', 'rowNo', 'programCode', 'programName', 'majorCode', 'gradeYear', 'courseCode']"\n      :download-template-fn="academicFileExchangeApi.downloadProgramTemplate"\n      :upload-fn="uploadProgramFile"\n      @imported="onProgramImported"\n    />\n  </ModulePageShell>\n</template>\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'\n''',
    '''import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'\nimport { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'\nimport AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker },\n''',
    '''  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker, AaAuthoritativeImportDrawer },\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''      summary: null,\n      showCreate: false,\n''',
    '''      summary: null,\n      academicFileExchangeApi,\n      importChooserVisible: false, importVisible: false, programImportPhase: 'DEFINITION',\n      showCreate: false,\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''    reviewStatusColor,\n    statusLabel(value) { return REVIEW_STATUS[value] || value || '' },\n''',
    '''    reviewStatusColor,\n    statusLabel(value) { return REVIEW_STATUS[value] || value || '' },\n    openProgramImport(phase) {\n      this.programImportPhase = phase === 'BINDING' ? 'BINDING' : 'DEFINITION'\n      this.importChooserVisible = false\n      this.importVisible = true\n    },\n    uploadProgramFile(file) {\n      return this.programImportPhase === 'BINDING'\n        ? academicFileExchangeApi.uploadProgramBindingImport(file)\n        : academicFileExchangeApi.uploadProgramDefinitionImport(file)\n    },\n    async downloadProgramTemplate() {\n      const res = await academicFileExchangeApi.downloadProgramTemplate()\n      if (res.code !== 0) { toast.error(res.message || '培养方案模板下载失败'); return }\n      const url = URL.createObjectURL(res.data)\n      const a = document.createElement('a'); a.href = url; a.download = '培养方案六工作表权威导入模板.xlsx'; a.click(); URL.revokeObjectURL(url)\n    },\n    async onProgramImported() { toast.success('培养方案权威导入已完成'); this.importVisible = false; await this.load() },\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaProgramListView.vue",
    '''.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }\n''',
    '''.aa-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }\n.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }\n''',
)

# ---------------------------------------------------------------------------
# Grade: remove browser rows as confirmation authority.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue",
    '''          <AppExcelImportDrawer\n            v-if="task"\n            v-model:visible="importVisible"\n            title="导入成绩（学号/平时/期中/期末/异常标记）"\n            template-name="成绩导入模板.xlsx"\n            :required-fields="['学号']"\n            :preview-fields="['studentNo', 'studentName', 'usualScore', 'midtermScore', 'finalScore', 'exceptionFlag']"\n            :download-template-fn="() => academicAffairsApi.downloadGradeImportTemplate(task.gradeTaskId)"\n            :upload-fn="(file) => academicAffairsApi.uploadGradeImportXlsx(task.gradeTaskId, file)"\n            :confirm-fn="({ rows }) => academicAffairsApi.confirmGradeImport(task.gradeTaskId, rows)"\n            :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadGradeImportErrors(task.gradeTaskId, rows, errors)"\n            @imported="onImported"\n          />\n''',
    '''          <AaAuthoritativeImportDrawer\n            v-if="task"\n            v-model:visible="importVisible"\n            title="成绩权威 XLSX 导入"\n            template-name="成绩导入模板.xlsx"\n            :preview-fields="['studentNo', 'studentName', 'usualScore', 'midtermScore', 'finalScore', 'exceptionFlag']"\n            :download-template-fn="() => academicAffairsApi.downloadGradeImportTemplate(task.gradeTaskId)"\n            :upload-fn="(file) => academicFileExchangeApi.uploadGradeImport(task.gradeTaskId, file)"\n            @imported="onImported"\n          />\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue",
    '''    ModulePageShell, EmptyState, LoadingState, ErrorState, AppButton, AppSectionCard,\n    AppStatusTag, AppInlineAlert, AppSelect, AppConfirmDialog, AppExcelImportDrawer, AppClassPicker,\n''',
    '''    ModulePageShell, EmptyState, LoadingState, ErrorState, AppButton, AppSectionCard,\n    AppStatusTag, AppInlineAlert, AppSelect, AppConfirmDialog, AaAuthoritativeImportDrawer, AppClassPicker,\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue",
    '''import { AppExcelImportDrawer } from '@/components/common/excel'\n''',
    '''import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue",
    '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\n''',
    '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue",
    '''      form: {\n''',
    '''      academicFileExchangeApi,\n      form: {\n''',
)

# ---------------------------------------------------------------------------
# Schedule: authoritative drawer + explicit ATOMIC/PARTIAL.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue",
    '''    <AppExcelImportDrawer\n      v-model:visible="importVisible"\n      title="批量导入课表"\n      template-name="排课结果导入模板.xlsx"\n      :required-fields="['教学任务ID', '星期', '节次']"\n      :preview-fields="['taskId', 'courseName', 'teacherName', 'className', 'weekday', 'slotNo', 'startWeek', 'endWeek', 'weekParity', 'classroom']"\n      :download-template-fn="() => academicAffairsApi.downloadScheduleImportTemplate()"\n      :upload-fn="uploadAuthoritative"\n      :confirm-fn="confirmAuthoritative"\n      @imported="onImported"\n    />\n''',
    '''    <AaAuthoritativeImportDrawer\n      v-model:visible="importVisible"\n      title="排课权威 XLSX 导入"\n      template-name="排课结果导入模板.xlsx"\n      show-import-mode\n      :preview-fields="['taskId', 'courseName', 'teacherName', 'className', 'weekday', 'slotNo', 'startWeek', 'endWeek', 'weekParity', 'classroom']"\n      :download-template-fn="() => academicAffairsApi.downloadScheduleImportTemplate()"\n      :upload-fn="(file, mode) => academicFileExchangeApi.uploadScheduleImport(batchId, file, mode)"\n      @imported="onImported"\n    />\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue",
    '''import { AppExcelImportDrawer } from '@/components/common/excel'\n''',
    '''import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue",
    '''    AppSelect, AppClassPicker, AppClassroomPicker, AppExcelImportDrawer, AaScheduleGrid\n''',
    '''    AppSelect, AppClassPicker, AppClassroomPicker, AaAuthoritativeImportDrawer, AaScheduleGrid\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue",
    '''      academicAffairsApi,\n      loading: false,\n''',
    '''      academicAffairsApi, academicFileExchangeApi,\n      loading: false,\n''',
)

# ---------------------------------------------------------------------------
# Roster: migrate server error-xlsx authority too.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue",
    '''    <AppExcelImportDrawer\n      v-model:visible="importVisible"\n      title="导入学籍名册"\n      template-name="学籍导入模板.xlsx"\n      :required-fields="['学号', '姓名', '班级']"\n      :preview-fields="['studentNo', 'realName', 'className', 'initialStatus']"\n      :download-template-fn="() => academicAffairsApi.downloadRosterImportTemplate()"\n      :upload-fn="uploadAuthoritative"\n      :confirm-fn="confirmAuthoritative"\n      :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadRosterImportErrors(rows, errors)"\n      @imported="onImported"\n    />\n''',
    '''    <AaAuthoritativeImportDrawer\n      v-model:visible="importVisible"\n      title="学籍名册权威 XLSX 导入"\n      template-name="学籍导入模板.xlsx"\n      :preview-fields="['studentNo', 'realName', 'className', 'initialStatus']"\n      :download-template-fn="() => academicAffairsApi.downloadRosterImportTemplate()"\n      :upload-fn="academicFileExchangeApi.uploadRosterImport"\n      @imported="onImported"\n    />\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue",
    '''import { AppExcelImportDrawer } from '@/components/common/excel'\n''',
    '''import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue",
    '''  components: { ModulePageShell, AppButton, AppSectionCard, AppExcelImportDrawer, AppConfirmDialog, AppSelect },\n''',
    '''  components: { ModulePageShell, AppButton, AppSectionCard, AaAuthoritativeImportDrawer, AppConfirmDialog, AppSelect },\n''',
)
patch(
    "frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue",
    '''      academicAffairsApi,\n      importVisible: false,\n''',
    '''      academicAffairsApi, academicFileExchangeApi,\n      importVisible: false,\n''',
)

print("W4 authoritative import patch applied")
