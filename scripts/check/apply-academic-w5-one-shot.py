from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"W5 patch anchor missing: {path}\n--- anchor ---\n{old[:600]}")
    if text.count(old) != 1:
        raise SystemExit(f"W5 patch anchor not unique: {path} count={text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# A) Real-semester pilot: hidden leaf route + permission-gated archive entry.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/academicAffairs/academic-affairs.routes.js",
    """    { path: 'archive', name: 'aa-archive', component: () => import('@/modules/academicAffairs/views/AaArchiveConsoleView.vue'), meta: meta('academicAffairs.archive.view', '教务归档') },\n    { path: 'archive/precheck', name: 'aa-archive-precheck', component: () => import('@/modules/academicAffairs/views/ArchivePrecheckView.vue'), meta: meta('academicAffairs.archive.view', '归档缺失提醒') },\n""",
    """    { path: 'archive', name: 'aa-archive', component: () => import('@/modules/academicAffairs/views/AaArchiveConsoleView.vue'), meta: meta('academicAffairs.archive.view', '教务归档') },\n    // W5 真实学期验收：隐藏叶子路由，不加入 navPlan；只对 archive.manage 开放。\n    { path: 'archive/semester-pilots', name: 'aa-semester-pilots', component: () => import('@/modules/academicAffairs/views/AaSemesterPilotView.vue'), meta: meta('academicAffairs.archive.manage', '真实学期验收') },\n    { path: 'archive/precheck', name: 'aa-archive-precheck', component: () => import('@/modules/academicAffairs/views/ArchivePrecheckView.vue'), meta: meta('academicAffairs.archive.view', '归档缺失提醒') },\n""",
)

patch(
    "frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue",
    """    <template #actions>\n      <AppButton variant=\"primary\" :disabled=\"actionBusy\" @click=\"openCreate\">新建归档批次</AppButton>\n    </template>\n""",
    """    <template #actions>\n      <AppButton v-if=\"canManageArchive\" :disabled=\"actionBusy\" @click=\"$router.push('/admin/academic-affairs/archive/semester-pilots')\">真实学期验收</AppButton>\n      <AppButton variant=\"primary\" :disabled=\"actionBusy\" @click=\"openCreate\">新建归档批次</AppButton>\n    </template>\n""",
)
patch(
    "frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue",
    """import AaArchiveCorrectionWorkspace from '@/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue'\nimport { toast } from '@/utils/toast'\n""",
    """import AaArchiveCorrectionWorkspace from '@/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue'\nimport { getPermissionPatterns } from '@/security/permissionGate'\nimport { matchPermission } from '@/config/navPlan'\nimport { toast } from '@/utils/toast'\n""",
)
patch(
    "frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue",
    """  async created() {\n    const c = await academicAffairsApi.getContext()\n    if (c.code === 0) this.ctx = c.data\n    this.load()\n  },\n  methods: {\n""",
    """  async created() {\n    const c = await academicAffairsApi.getContext()\n    if (c.code === 0) this.ctx = c.data\n    this.load()\n  },\n  computed: {\n    canManageArchive() {\n      const patterns = getPermissionPatterns()\n      return Array.isArray(patterns) && matchPermission(patterns, 'academicAffairs.archive.manage')\n    }\n  },\n  methods: {\n""",
)

# ---------------------------------------------------------------------------
# B) Counselor TEMP expiry: SQL filters + manual idempotent sync fallback.
# ---------------------------------------------------------------------------
patch(
    "backend/app/services/affairs_counselor_service.py",
    "from datetime import datetime\n",
    "from datetime import datetime, timedelta\n",
)
patch(
    "backend/app/services/affairs_counselor_service.py",
    """def list_assignments(user, class_id=None, user_id=None, status=None, vacancy_only=False,\n                     page=1, page_size=20):\n    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile, User\n    if status and status not in _STATUSES:\n        raise AppException(\"VALIDATION_ERROR\", \"状态仅支持 ACTIVE 或 ENDED\")\n""",
    """def list_assignments(user, class_id=None, user_id=None, status=None, vacancy_only=False,\n                     page=1, page_size=20, duty_type=None, expiry=None):\n    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile, User\n    if status and status not in _STATUSES:\n        raise AppException(\"VALIDATION_ERROR\", \"状态仅支持 ACTIVE 或 ENDED\")\n    duty_type = str(duty_type or \"\").strip().upper() or None\n    expiry = str(expiry or \"\").strip().upper() or None\n    if duty_type and duty_type not in _DUTY_TYPES:\n        raise AppException(\"VALIDATION_ERROR\", \"责任类型仅支持 PRIMARY/CO/TEMP\")\n    if expiry and expiry not in {\"WITHIN_7_DAYS\", \"EXPIRED\"}:\n        raise AppException(\"VALIDATION_ERROR\", \"到期筛选仅支持 WITHIN_7_DAYS/EXPIRED\")\n""",
)
patch(
    "backend/app/services/affairs_counselor_service.py",
    """        if user_id:\n            q = q.where(AffairsCounselorAssignment.user_id == int(user_id))\n        expired_temp = and_(\n            AffairsCounselorAssignment.status == \"ACTIVE\",\n            AffairsCounselorAssignment.duty_type == \"TEMP\",\n            AffairsCounselorAssignment.effective_to.is_not(None),\n            AffairsCounselorAssignment.effective_to <= datetime.utcnow(),\n        )\n""",
    """        if user_id:\n            q = q.where(AffairsCounselorAssignment.user_id == int(user_id))\n        if duty_type:\n            q = q.where(AffairsCounselorAssignment.duty_type == duty_type)\n        now = datetime.utcnow()\n        expired_temp = and_(\n            AffairsCounselorAssignment.status == \"ACTIVE\",\n            AffairsCounselorAssignment.duty_type == \"TEMP\",\n            AffairsCounselorAssignment.effective_to.is_not(None),\n            AffairsCounselorAssignment.effective_to <= now,\n        )\n        if expiry == \"EXPIRED\":\n            q = q.where(expired_temp)\n        elif expiry == \"WITHIN_7_DAYS\":\n            q = q.where(\n                AffairsCounselorAssignment.status == \"ACTIVE\",\n                AffairsCounselorAssignment.duty_type == \"TEMP\",\n                AffairsCounselorAssignment.effective_to.is_not(None),\n                AffairsCounselorAssignment.effective_to > now,\n                AffairsCounselorAssignment.effective_to <= now + timedelta(days=7),\n            )\n""",
)

patch(
    "backend/app/api/v1/student_affairs.py",
    """def counselor_assignments(classId: Optional[int] = None, userId: Optional[int] = None,\n                          status: Optional[str] = None, vacancyOnly: bool = False,\n                          page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),\n                          user=Depends(require_permission(\"studentAffairs.class.view\"))):\n    items, total = counselor_svc.list_assignments(user, classId, userId, status, vacancyOnly, page, pageSize)\n""",
    """def counselor_assignments(classId: Optional[int] = None, userId: Optional[int] = None,\n                          status: Optional[str] = None, dutyType: Optional[str] = None,\n                          expiry: Optional[str] = None, vacancyOnly: bool = False,\n                          page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),\n                          user=Depends(require_permission(\"studentAffairs.class.view\"))):\n    items, total = counselor_svc.list_assignments(\n        user, classId, userId, status, vacancyOnly, page, pageSize,\n        duty_type=dutyType, expiry=expiry,\n    )\n""",
)

patch(
    "frontend/src/modules/studentAffairs/api/class.api.js",
    """  publish(pid) { return call(() => request(`${B}/counselor-assessment/periods/${pid}/publish`, { method: 'POST' })) }\n""",
    """  publish(pid, version) { return call(() => request(`${B}/counselor-assessment/periods/${pid}/publish`, { method: 'POST', body: { version } })) }\n""",
)
patch(
    "frontend/src/modules/studentAffairs/api/class.api.js",
    """  vacancies() { return call(() => request(`${B}/counselor-vacancies`)) },\n  assign(body) { return call(() => request(`${B}/counselor-assignments`, { method: 'POST', body })) },\n""",
    """  vacancies() { return call(() => request(`${B}/counselor-vacancies`)) },\n  scanExpired() { return call(() => request(`${B}/counselor-assignments/scan-expired`, { method: 'POST', body: {} })) },\n  assign(body) { return call(() => request(`${B}/counselor-assignments`, { method: 'POST', body })) },\n""",
)

patch(
    "frontend/src/modules/studentAffairs/views/class/CounselorAssignmentView.vue",
    """          <select v-if=\"tab === 'assignments'\" v-model=\"filters.status\" @change=\"load\">\n            <option value=\"\">全部状态</option><option value=\"ACTIVE\">有效</option><option value=\"ENDED\">已结束</option>\n          </select>\n        </div>\n        <AppPermissionButton :allowed=\"canBtn('studentAffairs.class.create')\" code=\"studentAffairs.class.create\" type=\"button\" @click=\"openAssign\">分配责任</AppPermissionButton>\n""",
    """          <select v-if=\"tab === 'assignments'\" v-model=\"filters.status\" @change=\"load\">\n            <option value=\"\">全部状态</option><option value=\"ACTIVE\">有效</option><option value=\"ENDED\">已结束</option>\n          </select>\n          <select v-if=\"tab === 'assignments'\" v-model=\"filters.dutyType\" @change=\"load\">\n            <option value=\"\">全部责任类型</option><option value=\"PRIMARY\">主辅导员</option><option value=\"CO\">协同辅导员</option><option value=\"TEMP\">临时代班</option>\n          </select>\n          <select v-if=\"tab === 'assignments'\" v-model=\"filters.expiry\" @change=\"load\">\n            <option value=\"\">全部到期状态</option><option value=\"WITHIN_7_DAYS\">7天内到期</option><option value=\"EXPIRED\">已到期未同步</option>\n          </select>\n        </div>\n        <div class=\"responsibility-actions\">\n          <AppPermissionButton :allowed=\"canBtn('studentAffairs.class.create')\" code=\"studentAffairs.class.create\" type=\"button\" @click=\"scanExpiredTemps\">同步到期代班</AppPermissionButton>\n          <AppPermissionButton :allowed=\"canBtn('studentAffairs.class.create')\" code=\"studentAffairs.class.create\" type=\"button\" @click=\"openAssign\">分配责任</AppPermissionButton>\n        </div>\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/class/CounselorAssignmentView.vue",
    """  data: () => ({ tabs: TABS, tab: 'ledger', rows: [], loading: true, error: '', filters: { classId: '', status: '' }, pagination: { page: 1, pageSize: 20, total: 0 }, dialog: { visible: false, mode: '', title: '', row: null }, form: emptyForm(), dialogError: '', submitting: false }),\n""",
    """  data: () => ({ tabs: TABS, tab: 'ledger', rows: [], loading: true, error: '', filters: { classId: '', status: '', dutyType: '', expiry: '' }, pagination: { page: 1, pageSize: 20, total: 0 }, dialog: { visible: false, mode: '', title: '', row: null }, form: emptyForm(), dialogError: '', submitting: false }),\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/class/CounselorAssignmentView.vue",
    """      else res = await counselorAssignmentApi.assignments({ ...this.pagination, classId: this.filters.classId || undefined, status: this.filters.status || undefined })\n""",
    """      else res = await counselorAssignmentApi.assignments({\n        ...this.pagination, classId: this.filters.classId || undefined, status: this.filters.status || undefined,\n        dutyType: this.filters.dutyType || undefined, expiry: this.filters.expiry || undefined\n      })\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/class/CounselorAssignmentView.vue",
    """    onPageChange(page) { this.pagination.page = page; this.load() },\n    openAssign(row = null) {\n""",
    """    onPageChange(page) { this.pagination.page = page; this.load() },\n    async scanExpiredTemps() {\n      if (this.submitting) return\n      this.submitting = true; this.error = ''\n      const res = await counselorAssignmentApi.scanExpired()\n      this.submitting = false\n      if (res.code !== 0) { this.error = res.message || '到期代班同步失败'; return }\n      const ended = Number(res.data?.ended || 0)\n      window.dispatchEvent(new CustomEvent('app:toast', { detail: { type: 'success', message: `到期代班同步完成：结束 ${ended} 条；接口幂等，可安全重跑` } }))\n      this.pagination.page = 1\n      await this.load()\n      // vacancy 页不做前端缓存；切换时重新请求 /counselor-vacancies，避免展示扫描前旧结果。\n    },\n    openAssign(row = null) {\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/class/CounselorAssignmentView.vue",
    """      <p class=\"responsibility-note\"><strong>影响说明：</strong>数据按当前角色与数据范围裁剪。主辅导员变更会结束旧主责关系并同步班级主辅导员；历史记录保留用于追溯。</p>\n""",
    """      <p class=\"responsibility-note\"><strong>到期治理：</strong>生产环境通常由定时任务自动结束临时代班；“同步到期代班”是人工立即兜底，服务端幂等执行并保留 TEMP_EXPIRE 审计。责任/到期筛选全部由后端 SQL 执行，不在浏览器拉全量后过滤。</p>\n      <p class=\"responsibility-note\"><strong>影响说明：</strong>数据按当前角色与数据范围裁剪。主辅导员变更会结束旧主责关系并同步班级主辅导员；历史记录保留用于追溯。</p>\n""",
)

# ---------------------------------------------------------------------------
# C) SLA transparency: one server truth, read-only strips on risk/leave pages.
# ---------------------------------------------------------------------------
patch(
    "frontend/src/modules/studentAffairs/api/studentAffairs.api.js",
    """  getDashboard() {\n    return callStrict(() => request('/student-affairs/dashboard'))\n  },\n\n  // ─────────────── 班级（供选择器/代录用） ───────────────\n""",
    """  getDashboard() {\n    return callStrict(() => request('/student-affairs/dashboard'))\n  },\n\n  /** 当前学校风险/请假 SLA 生效真值；页面只展示，不复制 dueAt/overdue 算法。 */\n  getSlaConfig() {\n    return callStrict(() => request('/student-affairs/sla-config'))\n  },\n\n  // ─────────────── 班级（供选择器/代录用） ───────────────\n""",
)

patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue",
    """      <div class=\"sa-grid sa-grid--metrics\">\n""",
    """      <StudentAffairsSlaStrip kind=\"risk\" />\n      <div class=\"sa-grid sa-grid--metrics\">\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue",
    """import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'\n""",
    """import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'\nimport StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue",
    """    DataTable,\n    TaskContextBar\n""",
    """    DataTable,\n    TaskContextBar,\n    StudentAffairsSlaStrip\n""",
)

patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskDetailView.vue",
    """      <section class=\"sa-summary-strip risk-summary\">\n""",
    """      <StudentAffairsSlaStrip kind=\"risk\" />\n      <section class=\"sa-summary-strip risk-summary\">\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskDetailView.vue",
    """import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'\n""",
    """import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'\nimport StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/StudentAffairsRiskDetailView.vue",
    """    AppSensitiveText,\n    AppRiskOwnerPicker\n""",
    """    AppSensitiveText,\n    AppRiskOwnerPicker,\n    StudentAffairsSlaStrip\n""",
)

patch(
    "frontend/src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue",
    """      <div class=\"bar\">\n""",
    """      <StudentAffairsSlaStrip kind=\"leave\" />\n      <div class=\"bar\">\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue",
    """import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'\n""",
    """import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'\nimport StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'\n""",
)
patch(
    "frontend/src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue",
    """    ModulePageShell, EmptyState, TaskContextBar, DualPaneWorkspace, AppStatusTag, AppConfirmDialog, AppPermissionButton,\n""",
    """    ModulePageShell, EmptyState, TaskContextBar, StudentAffairsSlaStrip, DualPaneWorkspace, AppStatusTag, AppConfirmDialog, AppPermissionButton,\n""",
)

print("W5 semester pilot, TEMP expiry, SLA and legacy API closeout patch applied")
