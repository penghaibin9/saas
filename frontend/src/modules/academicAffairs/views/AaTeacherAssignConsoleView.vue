<template>
  <ModulePageShell
    title="任课教师分配"
    subtitle="分配后由任课教师本人确认"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template v-if="batchId" #actions>
      <AppButton @click="openBatch({ batchId })">返回批次</AppButton>
    </template>
    <div class="mp-stack task-workspace">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingAssignment" :disabled="assign.submitting || loading" @click="queryPendingAssignment">查询原分配结果（不会重复提交）</AppButton>
      <div v-if="batchId" class="task-workspace__context"><strong>{{ rows[0]?.batchName || '当前教学任务批次' }}</strong><span>{{ rows[0]?.termName || '按来源学期办理' }}</span><AppButton @click="$router.push({ path: '/admin/academic-affairs/teaching-tasks/merge-split', query: { batchId, termId, returnTo: $route.fullPath } })">合班拆班</AppButton></div>
      <div class="aa-filter task-workspace__filters">
        <label>学期<AppTermEntityPicker v-model="termId" clearable @change="changeFilter" /></label>
        <label>搜索任务<input v-model.trim="keyword" placeholder="课程、教学班或教师" @keyup.enter="changeFilter" /></label>
        <label class="aa-filter__item">状态
          <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="" class="aa-select" @change="changeFilter" />
        </label>
        <AppButton :disabled="assign.submitting" @click="changeFilter">查询</AppButton>
        <AppButton :loading="loading" :disabled="assign.submitting" @click="load">刷新</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="filterStatus ? '当前筛选下没有教学任务' : '暂无教学任务'"
                 :description="filterStatus ? '可切换状态筛选查看其他任务' : '请先在「教学任务生成」按学期生成应开课程'" />
      <div class="task-workspace__split">
      <DataTable v-if="!loading && !error && rows.length" :columns="columns" :rows="rows" row-key="taskId" :row-class="row => String(row.taskId) === String(assign.taskId) && assign.visible ? 'task-workspace__selected' : ''" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName || row.courseCode }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.termName || row.termCode || '学期待核对' }}</div>
          <button class="mp-link mp-cell-sub" @click="openBatch(row)">查看批次</button>
        </template>
        <template #cell-teacher="{ row }">
          <span v-if="row.teacherName">{{ teacherText(row.teacherName) }}</span>
          <span v-else class="mp-cell-sub">未分配</span>
        </template>
        <template #cell-hours="{ row }">{{ row.weeklyHours ?? '—' }} 学时 · {{ row.expectedStudents ?? '—' }} 人</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div v-if="row.rejectReason" class="mp-cell-sub is-danger">退回：{{ row.rejectReason }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="canAssign(row)" class="mp-link" :disabled="assign.submitting" @click="openAssign(row)">{{ row.teacherKey ? '改派' : '分配' }}</button>
          <button v-else-if="canAdjust && (row.status === 'TEACHER_CONFIRMED' || row.status === 'READY')" class="mp-link" title="教师已确认，换人需走任务调整" @click="openAdjust(row)">调整</button>
          <span v-else class="mp-cell-sub">—</span>
        </template>
      </DataTable>
      <aside v-if="assign.visible" class="task-workspace__panel" aria-label="分配任课教师">
        <h3>分配任课教师</h3>
      <AaObjectContext :name="assign.courseName" :source="assign.teachingClassName" />
      <div class="aa-assign-form">
        <label>任课教师<AppTeacherPicker v-model="assign.teacherKey" :query="teacherKeyQuery" placeholder="选择任课教师" @change="onTeacherPicked" /></label>
        <label>周学时<input v-model.number="assign.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>预计人数<input v-model.number="assign.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
      <p class="mp-cell-sub">分配后等待教师本人确认。</p>

        <AppInlineAlert v-if="error" type="danger" :description="error" />
        <div class="task-workspace__actions"><AppButton variant="primary" :loading="assign.submitting" :disabled="Boolean(pendingAssignment) || !canManage" @click="doAssign">保存分配</AppButton><AppButton :disabled="assign.submitting" @click="assign.visible = false">取消</AppButton></div>
      </aside>
      <aside v-else class="task-workspace__panel"><h3>选择待分配任务</h3><p>从左侧任务打开分配；保存后由任课教师本人确认。</p><p>已确认任务换教师，请到“教学任务调整”办理。</p></aside>
      </div>
    </div>


  </ModulePageShell>
</template>

<script>
/**
 * 任课教师分配（/admin/academic-affairs/teaching-tasks/assign）：跨批次工作队列。
 * GET /academic-affairs/teaching-tasks（跨批次）+ POST /teaching-tasks/{taskId}/assign。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppSelect, AppTeacherPicker, AppTermEntityPicker, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { teachingTaskWorkbenchApi } from '../api/teaching-task-workbench.api'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaObjectContext from '../components/parallel-a/AaObjectContext.vue'
import { readTaskPages } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTeacherAssignConsoleView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppSelect, AppTeacherPicker, AppTermEntityPicker, AppInlineAlert, AaOperationReceipt, AaObjectContext },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      termId: '', keyword: '',
      loading: true, error: '', rows: [], filterStatus: '', teacherKeyQuery: { valueField: 'loginName' }, revision: 0, receipt: null, pendingAssignment: null,
      statusOptions: [
        { value: '', label: '全部状态' },
        { value: 'PENDING_ASSIGN', label: '待分配' },
        { value: 'REJECTED_BY_TEACHER', label: '教师退回' },
        { value: 'ASSIGNED', label: '已分配（待教师确认）' },
        { value: 'TEACHER_CONFIRMED', label: '教师已确认' }
      ],
      pagination: { page: 1, pageSize: 20, total: 0 },
      assign: { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '', weeklyHours: null, expectedStudents: null },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'batch', title: '学期 / 批次' },
        { key: 'teacher', title: '任课教师' },
        { key: 'hours', title: '周学时 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    batchId() { return String(this.$route.query.batchId || '') },
    queueQuery() { const q = this.$route.query; return JSON.stringify([q.batchId, q.termId, q.keyword, q.status, q.page]) },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.assign') },
    canAdjust() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.adjust') }
  },
  watch: {
    queueQuery() { this.assign.visible = false; this.restoreQuery(); this.load() },
    ctx() { this.assign = { visible: false, submitting: false }; this.receipt = null; this.pendingAssignment = null; this.pagination.page = 1; this.load() }
  },
  created() { this.restoreQuery(); this.load() },
  beforeUnmount() { this.revision++; this.disposed = true },
  methods: {
    canAssign(row) { return (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' && !this.pendingAssignment && this.canManage && ['PENDING_ASSIGN', 'ASSIGNED', 'REJECTED_BY_TEACHER'].includes(row.status) },
    changeFilter() { return this.onPageChange(1) },
    restoreQuery() { const q = this.$route.query; this.termId = String(q.termId || ''); this.keyword = String(q.keyword || ''); this.filterStatus = String(q.status || ''); this.pagination.page = Math.max(1, Number(q.page) || 1) },
    // 教师姓名里带的登录账号（如“张三（zhangsan）”）不展示
    teacherText(name) { return String(name || '').replace(/\s*[（(][A-Za-z0-9_.@-]+[)）]\s*$/, '') },
    openAdjust(row) { this.$router.push({ path: '/admin/academic-affairs/teaching-tasks/adjust', query: { batchId: String(row.batchId), taskId: String(row.taskId), termId: this.termId || undefined, returnTo: this.$route.fullPath } }) },
    openBatch(row) { this.$router.push({ path: `/admin/academic-affairs/teaching-tasks/${row.batchId}`, query: { returnTo: this.$route.fullPath } }) },
    onTeacherPicked(value, items) {
      this.assign.teacherKey = value || ''
      this.assign.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || (s ? '状态待确认' : '') },
    async onPageChange(p) { if (this.assign.submitting) return; this.pagination.page = p; const before = this.$route.fullPath; await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: this.termId || undefined, keyword: this.keyword || undefined, status: this.filterStatus || undefined, page: String(p) } }); if (before === this.$route.fullPath) await this.load() },
    async load() {
      const revision = ++this.revision
      this.loading = true
      this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.listAllTasks({
          termId: this.termId || undefined, keyword: this.keyword || undefined,
          batchId: this.batchId || undefined, status: this.filterStatus || undefined,
          page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        if (revision !== this.revision) return
        if (res.code === 0) {
          this.rows = res.data.list; this.pagination.total = res.data.total
          const selected = this.rows.find(row => String(row.taskId) === String(this.$route.query.selectedTaskId || ''))
          if (selected && !this.assign.taskId && !this.pendingAssignment) { this.loading = false; this.openAssign(selected) }
        }
        else this.handleFailure(res, '派师队列读取失败')
      } catch (error) { if (revision === this.revision) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (revision === this.revision) this.loading = false }
    },
    openAssign(row) {
      if (!this.canAssign(row) || this.assign.submitting || this.loading) return
      this.assign = { visible: true, submitting: false, taskId: row.taskId, batchId: row.batchId, courseName: row.courseName, teachingClassName: row.teachingClassName, teacherName: row.teacherName || '',
                      teacherKey: row.teacherKey || '', weeklyHours: row.weeklyHours, expectedStudents: row.expectedStudents }
      if (String(this.$route.query.selectedTaskId || '') !== String(row.taskId)) this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, selectedTaskId: String(row.taskId) } })
    },
    handleFailure(result, fallback) {
      const message = result?.message || fallback
      if (isDeniedResult(result)) {
        this.revision++; this.loading = false; this.rows = []; this.pagination.total = 0; this.receipt = null
        this.assign = { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '' }
        this.error = `${message}；已清除先前内容。`
      } else {
        this.error = message
        if (isConflictResult(result)) this.receipt = { title: '重新核对派师', object: this.assign.courseName || '教学任务', status: '数据已变化，保留输入', pending: true, next: '请刷新来源批次后重新核对，不会自动重提。' }
      }
    },
    async doAssign() {
      const form = this.assign
      if (this.pendingAssignment || !this.canManage || form.submitting || !form.taskId || !form.batchId) return
      if (!form.teacherKey || !form.teacherName) { toast.error('请选择带正式工号的任课教师'); return }
      const scope = this.batchId
      const teacherKey = form.teacherKey
      form.submitting = true
      const context = this.ctx
      const current = () => !this.disposed && scope === this.batchId && this.assign === form && context === this.ctx
      const object = [form.courseName || '教学任务', form.teachingClassName].filter(Boolean).join(' · ')
      let commandPhase = false
      try {
        const batch = await teachingTaskWorkbenchApi.getBatch(form.batchId)
        if (!current()) return
        if (batch.code !== 0) { this.handleFailure(batch, '批次核对失败，尚未提交。'); return }
        if (!batch.data?.actions?.canAssign) { this.handleFailure({ code: 409001, message: '批次已不允许派师，请核对当前状态。' }); return }
        this.pendingAssignment = { taskId: String(form.taskId), batchId: String(form.batchId), teacherKey, object }
        commandPhase = true
        const result = await academicAffairsApi.assignTeacher(form.taskId, {
          teacherName: form.teacherName, teacherKey, weeklyHours: form.weeklyHours ?? undefined, expectedStudents: form.expectedStudents ?? undefined
        })
        commandPhase = false
        if (!current()) return
        if (result.code !== 0) { if (isDeniedResult(result) || isConflictResult(result) || String(result.code).startsWith('400') || result.bizCode === 'VALIDATION_ERROR') this.pendingAssignment = null; this.handleFailure(result, '分配失败'); return }
        const readback = await readTaskPages(page => academicAffairsApi.getBatchTasks(form.batchId, page), current)
        if (!current()) return
        if (readback?.code !== 0) {
          this.receipt = { object, status: '结果待确认', pending: true, next: '未能完整读取正式任务，请刷新来源批次核对，不要重复分配。' }
          this.handleFailure(readback, '正式任务读取失败'); return
        }
        const row = readback.data.list.find(item => String(item.taskId) === String(form.taskId))
        const confirmed = row?.teacherKey === teacherKey && ['ASSIGNED', 'TEACHER_CONFIRMED', 'READY'].includes(row.status)
        if (confirmed) this.pendingAssignment = null
        form.visible = false
        await this.load()
        if (!current() || this.error) return
        this.receipt = { object, status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, next: confirmed ? '由任课教师本人确认，之后交学院和教务核对。' : '正式记录尚未反映本次分配，请打开来源批次核对。' }
      } catch (error) {
        if (current()) {
          if (commandPhase && (isDeniedResult(error) || isConflictResult(error) || String(error?.code).startsWith('400') || error?.bizCode === 'VALIDATION_ERROR')) this.pendingAssignment = null
          this.receipt = { object, status: '结果待确认', pending: true, next: '请重新读取来源批次，不要重复提交。' }; this.handleFailure(error, '连接中断，请核对正式任务。')
        }
      } finally { form.submitting = false }
    },
    async queryPendingAssignment() {
      if (!this.pendingAssignment || this.assign.submitting || this.loading) return
      const pending = this.pendingAssignment, context = this.ctx
      this.assign.submitting = true
      try {
        const result = await academicAffairsApi.listAllTasks({ taskId: pending.taskId, batchId: pending.batchId, page: 1, pageSize: 1 })
        if (this.disposed || context !== this.ctx || this.pendingAssignment !== pending) return
        if (result.code !== 0) { this.handleFailure(result, '原分配结果读取失败'); return }
        const row = result.data?.list?.find(item => String(item.taskId) === pending.taskId)
        const confirmed = row?.teacherKey === pending.teacherKey && ['ASSIGNED', 'TEACHER_CONFIRMED', 'READY'].includes(row.status)
        this.receipt = { object: pending.object, status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, next: confirmed ? '由任课教师本人确认，再交学院核对。' : '尚未读到一致的正式结果，请联系学院核对；不会重复提交。' }
        if (confirmed) { this.pendingAssignment = null; this.assign.visible = false; await this.load() }
      } catch (error) { if (context === this.ctx) this.handleFailure(error, '原分配结果查询失败') }
      finally { if (context === this.ctx) this.assign.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/teaching-task-workspace.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { min-width: 220px; }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.mp-cell-sub.is-danger { color: var(--danger-600, #d54941); }
</style>
