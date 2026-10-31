<template>
  <ModulePageShell
    title="教学任务调整"
    subtitle="教师已确认的任务在这里更正"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton v-if="returnTo" :disabled="adjust.submitting" @click="$router.push(returnTo)">返回来源</AppButton>
      <AppButton v-if="adjust.visible" :disabled="adjust.submitting || Boolean(pendingAdjustment)" @click="adjust.visible = false">重新选择任务</AppButton>
    </template>
    <div class="mp-stack task-workspace">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingAdjustment" :disabled="adjust.submitting || loading" @click="queryPendingAdjustment">查询原调整结果（不会重复提交）</AppButton>
      <AppInlineAlert v-if="scopeReadOnlyReason" type="info" :description="scopeReadOnlyReason" />
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <details v-if="!adjust.visible" class="mp-note">
        <summary>哪些调整需要重新确认？</summary>
        <p>仅调整姓名、学时、周次或人数，不触发换人确认。更换任课教师后须由新教师本人确认；原批次已完成的学院确认、学校终审也须重新办理。</p>
        <p>已有课表请走排课变更；已并入合班的任务须先处理合拆班。</p>
      </details>

      <div v-if="!adjust.visible" class="task-workspace__filters">
        <label>学期<AppTermEntityPicker v-model="termId" clearable @change="changeFilter" /></label>
        <label>搜索任务<input v-model.trim="keyword" placeholder="课程、教学班或教师" @keyup.enter="changeFilter" /></label>
        <label class="aa-filter__item">状态
          <AppSelect v-model="filterStatus" :options="statusOptions" :placeholder="''" @change="changeFilter" />
        </label>
        <AppButton :disabled="adjust.submitting" @click="changeFilter">查询</AppButton><AppButton :loading="loading" :disabled="adjust.submitting" @click="load">刷新</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无可调整的教学任务"
                 description="请先在「教学任务生成」按学期生成应开课程，或调整已合班/已排课的任务需先在对应模块处理" />
      <DataTable v-if="!adjust.visible && !loading && !error && rows.length" :columns="columns" :rows="rows" row-key="taskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName || row.courseCode }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-batch="{ row }">{{ row.termName || row.termCode || '—' }}</template>
        <template #cell-teacher="{ row }">
          <span v-if="row.teacherName">{{ row.teacherName }}</span>
          <span v-else class="mp-cell-sub">未分配</span>
        </template>
        <template #cell-hours="{ row }">
          周 {{ row.weeklyHours ?? '—' }} · 共 {{ row.totalHours ?? '—' }} 学时 · 第 {{ row.startWeek ?? '—' }}-{{ row.endWeek ?? '—' }} 周 · 计 {{ row.expectedStudents ?? '—' }} 人
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="canInspectAdjustment" class="mp-link" :disabled="adjust.submitting || actionLoading" @click="openAdjust(row)">查看调整条件</button>
          <span v-else class="mp-cell-sub">当前只读</span>
        </template>
      </DataTable>
    <section v-if="adjust.visible" class="task-workspace__panel" aria-label="调整教学任务">
      <div class="task-adjust-heading"><h3>{{ adjust.courseName }}</h3><p>{{ adjust.teachingClassName }}</p></div>
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <div class="task-adjust-layout">
      <table class="task-workspace__comparison"><thead><tr><th>调整项目</th><th>当前安排</th><th>调整后</th></tr></thead><tbody>
        <tr><th>任课教师</th><td>{{ adjust.origTeacherName || '未分配' }}</td><td><AppTeacherPicker v-model="adjust.teacherKey" :query="teacherKeyQuery" placeholder="选择任课教师" @change="onTeacherPicked" /></td></tr>
        <tr v-for="field in adjustmentFields" :key="field.key"><th>{{ field.label }}</th><td>{{ adjust.original?.[field.key] ?? '—' }}</td><td><input v-model.number="adjust[field.key]" type="number" :min="field.min" :aria-label="`调整后${field.label}`" class="aa-input" /></td></tr>
      </tbody></table>
      <aside class="task-adjust-impact">
        <h3>调整后的办理</h3>
        <template v-if="teacherChangedInDialog"><ol><li>由新任教师本人重新确认</li><li>原批次已完成的学院核对须重新办理</li><li>原批次已完成的校教务终审须重新办理</li></ol></template>
        <p v-else>本次未更换任课教师。姓名、学时、周次和人数更正不触发换人确认，仍须通过正式任务校验。</p>
        <p class="task-workspace__notice task-workspace__notice--warning">已有课表的任务不能在此直接调整，请通过排课与课表办理正式变更。</p>
        <p class="mp-cell-sub">提交前核对最新状态及课表引用；失败保留已填内容。</p>
      </aside></div>
      <label class="aa-note-label">调整原因<i class="aa-req">*</i>（必填，至少 5 字，写入审计）
        <input ref="adjustReason" v-model.trim="adjust.reason" class="aa-input" :aria-invalid="Boolean(reasonError)" placeholder="请说明调整原因" maxlength="500" @input="reasonError = ''" />
      </label>
      <p v-if="reasonError" role="alert" class="task-adjust-error">{{ reasonError }}</p>
      <div class="task-workspace__actions"><AppButton variant="primary" :loading="adjust.submitting" :disabled="!canAdjust || actionLoading || Boolean(pendingAdjustment)" @click="doAdjust">核对并提交调整</AppButton><AppButton :disabled="adjust.submitting" @click="adjust.visible = false">取消</AppButton></div>
    </section>
    </div>


  </ModulePageShell>
</template>

<script>
/**
 * 教学任务调整（/admin/academic-affairs/teaching-tasks/adjust，续工新增）。
 * GET /academic-affairs/teaching-tasks（跨批次，排除 MERGED）+ POST /teaching-tasks/{taskId}/adjust。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppInlineAlert, AppSelect, AppTermEntityPicker, AppTeacherPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingTaskWorkbenchApi } from '@/modules/academicAffairs/api/teaching-task-workbench.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { readTaskPages } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTaskAdjustView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppInlineAlert, AppSelect, AppTermEntityPicker, AppTeacherPicker, AaOperationReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      termId: '', keyword: '', reasonError: '',
      adjustmentFields: [{ key: 'weeklyHours', label: '周学时', min: 0 }, { key: 'totalHours', label: '总学时', min: 0 }, { key: 'startWeek', label: '开始周', min: 1 }, { key: 'endWeek', label: '结束周', min: 1 }, { key: 'expectedStudents', label: '预计人数', min: 0 }],
      loading: true, error: '', all: [], filterStatus: '', teacherKeyQuery: { valueField: 'loginName' },
      revision: 0, receipt: null, pendingAdjustment: null, actionSeq: 0, actionLoading: false, actionError: '', batchWorkbench: {},
      pagination: { page: 1, pageSize: 20, total: 0 },
      adjust: { visible: false, submitting: false, taskId: '', origTeacherName: '', origTeacherKey: '',
               teacherName: '', teacherKey: '', weeklyHours: null, totalHours: null,
               startWeek: null, endWeek: null, expectedStudents: null, reason: '' },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'batch', title: '批次' },
        { key: 'teacher', title: '授课教师' },
        { key: 'hours', title: '学时 / 周次 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    returnTo() { const value = this.$route.query.returnTo; return typeof value === 'string' && /^\/admin\/academic-affairs\/teaching-tasks(?:[/?]|$)/.test(value) ? value : '' },
    mutationContext() { return JSON.stringify([this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    scopeReadOnlyReason() { return (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' ? '' : '学校仅查看，教学任务调整由开课责任学院办理。' },
    canInspectAdjustment() { return !this.scopeReadOnlyReason && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.adjust') },
    canAdjust() { return this.canInspectAdjustment && this.batchWorkbench.actions?.canAdjust === true && String(this.batchWorkbench.batchId || '') === String(this.adjust.batchId || '') },
    statusOptions() {
      return [
        { value: '', label: '全部（不含已并入合班）' },
        { value: 'PENDING_ASSIGN', label: '待分配' },
        { value: 'ASSIGNED', label: '已分配(待教师确认)' },
        { value: 'REJECTED_BY_TEACHER', label: '教师退回' },
        { value: 'TEACHER_CONFIRMED', label: '教师已确认' },
        { value: 'READY', label: '已就绪(可排课)' }
      ]
    },
    rows() {
      // MERGED 成员任务不可调整（须先拆班），列表侧直接排除，避免用户点进死路
      return this.all.filter((r) => r.status !== 'MERGED')
    },
    teacherChangedInDialog() {
      const a = this.adjust
      return (a.teacherKey || '') !== (a.origTeacherKey || '')
    }
  },
  created() { this.restoreQuery(); this.load() },
  watch: { '$route.fullPath'() { this.adjust.visible = false; this.restoreQuery(); this.load() }, ctx: { deep: true, handler() { this.revision++; this.actionSeq++; this.all = []; this.receipt = null; this.pendingAdjustment = null; this.batchWorkbench = {}; this.actionError = ''; this.actionLoading = false; this.adjust = { visible: false, submitting: false }; this.load() } } },
  beforeUnmount() { this.revision++; this.actionSeq++; this.disposed = true },
  methods: {
    changeFilter() { return this.onPageChange(1) },
    restoreQuery() { const q = this.$route.query; this.termId = String(q.termId || ''); this.keyword = String(q.keyword || ''); this.filterStatus = String(q.status || ''); this.pagination.page = Math.max(1, Number(q.page) || 1) },
    onTeacherPicked(value, items) {
      this.adjust.teacherKey = value || ''
      this.adjust.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || (s ? '状态待确认' : '') },
    async onPageChange(p) { if (this.adjust.submitting) return; this.pagination.page = p; const before = this.$route.fullPath; await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, taskId: undefined, termId: this.termId || undefined, keyword: this.keyword || undefined, status: this.filterStatus || undefined, page: String(p) } }); if (before === this.$route.fullPath) await this.load() },
    async load() {
      const revision = ++this.revision, context = this.mutationContext, ctx = this.ctx
      const valid = () => !this.disposed && revision === this.revision && context === this.mutationContext && ctx === this.ctx
      this.loading = true
      this.error = ''
      this.all = []; this.pagination.total = 0
      try {
      const res = await academicAffairsApi.listAllTasks({
        batchId: this.$route.query.batchId || undefined, taskId: this.$route.query.taskId || undefined, termId: this.termId || undefined, keyword: this.keyword || undefined, excludeMerged: true,
        status: this.filterStatus || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (!valid()) return
      if (res.code === 0) { this.all = res.data.list; this.pagination.total = res.data.total }
      else { this.handleFailure(res, '教学任务读取失败') }
      } catch (error) { if (valid()) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (valid()) this.loading = false }
    },
    async readAdjustmentActions(batchId) {
      const seq = ++this.actionSeq, context = this.mutationContext, ctx = this.ctx
      const valid = () => !this.disposed && seq === this.actionSeq && context === this.mutationContext && ctx === this.ctx
      this.batchWorkbench = {}; this.actionLoading = true; this.actionError = ''
      try {
        const res = await teachingTaskWorkbenchApi.getBatch(String(batchId))
        if (!valid()) return false
        if (res.code !== 0) throw res
        if (String(res.data?.batchId || '') !== String(batchId)) throw { message: '批次读取返回了不同对象，请重新核对。' }
        this.batchWorkbench = res.data
        if (!this.canInspectAdjustment || res.data.actions?.canAdjust !== true) { this.actionError = '本批次当前不允许调整，请由开课责任学院的有效办理人核对任职、权限及批次状态。'; return false }
        return true
      } catch (error) {
        if (valid()) { this.actionError = error?.message || '批次办理条件读取失败，请重试。'; if (isDeniedResult(error)) { this.all = []; this.receipt = null; this.adjust = { visible: false, submitting: false } } }
        return false
      } finally { if (valid()) this.actionLoading = false }
    },
    async openAdjust(row) {
      if (this.pendingAdjustment || !this.canInspectAdjustment || this.adjust.submitting || this.actionLoading || this.loading || row.status === 'MERGED') return
      this.reasonError = ''
      this.adjust = {
        visible: false, submitting: false, taskId: String(row.taskId),
        batchId: String(row.batchId), courseName: row.courseName, teachingClassName: row.teachingClassName,
        original: { ...row }, origTeacherName: row.teacherName || '', origTeacherKey: row.teacherKey || '',
        teacherName: row.teacherName || '', teacherKey: row.teacherKey || '',
        weeklyHours: row.weeklyHours, totalHours: row.totalHours,
        startWeek: row.startWeek, endWeek: row.endWeek, expectedStudents: row.expectedStudents,
        reason: ''
      }
      const form = this.adjust
      if (await this.readAdjustmentActions(form.batchId) && this.adjust === form) form.visible = true
    },
    async doAdjust() {
      if (this.pendingAdjustment || !this.canAdjust || this.adjust.submitting || !this.adjust.taskId) return
      if (!this.adjust.reason || this.adjust.reason.length < 5) { this.reasonError = '请填写至少5字的调整原因'; this.$refs?.adjustReason?.focus(); return }
      if (this.adjust.teacherName && !this.adjust.teacherKey) { toast.error('请选择带正式工号的任课教师'); return }
      if (this.adjust.startWeek && this.adjust.endWeek && this.adjust.startWeek > this.adjust.endWeek) { toast.error('开始周不能晚于结束周'); return }
      this.adjust.submitting = true
      const form = this.adjust
      const context = this.mutationContext, ctx = this.ctx
      const valid = () => !this.disposed && this.adjust === form && context === this.mutationContext && ctx === this.ctx
      const body = {
        teacherName: this.adjust.teacherName || undefined,
        teacherKey: this.adjust.teacherKey || undefined,
        weeklyHours: this.adjust.weeklyHours ?? undefined,
        totalHours: this.adjust.totalHours ?? undefined,
        startWeek: this.adjust.startWeek ?? undefined,
        endWeek: this.adjust.endWeek ?? undefined,
        expectedStudents: this.adjust.expectedStudents ?? undefined,
        reason: this.adjust.reason
      }
      let commandPhase = false
      try {
        if (!await this.readAdjustmentActions(form.batchId) || !valid() || !this.canAdjust) return
        this.receipt = { object: [form.courseName, form.teachingClassName].filter(Boolean).join(' · ') || '教学任务', status: '结果待确认', pending: true, next: '提交后重新读取正式任务；请勿重复调整。' }
        this.pendingAdjustment = { taskId: form.taskId, batchId: form.batchId, body: { ...body }, object: this.receipt.object }
        commandPhase = true
        const res = await academicAffairsApi.adjustTask(form.taskId, body)
        commandPhase = false
        if (!valid()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code).startsWith('400') || res.bizCode === 'VALIDATION_ERROR') this.pendingAdjustment = null; this.handleFailure(res, '调整失败'); return }
        const readback = await readTaskPages(page => academicAffairsApi.getBatchTasks(form.batchId, page), valid)
        if (!valid()) return
        if (readback?.code !== 0) { this.handleFailure(readback, '正式任务读取失败'); return }
        const row = readback.data.list.find(item => String(item.taskId) === String(form.taskId))
        const fields = ['teacherKey', 'weeklyHours', 'totalHours', 'startWeek', 'endWeek', 'expectedStudents']
        const confirmed = row && fields.every(key => body[key] === undefined || String(row[key]) === String(body[key]))
        if (confirmed) this.pendingAdjustment = null
        form.visible = false
        await this.load()
        if (valid() && !this.error) this.receipt = { object: [form.courseName, form.teachingClassName].filter(Boolean).join(' · ') || '教学任务', status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, next: confirmed ? (this.teacherChangedInDialog ? '由新教师本人确认；已完成学院确认或学校终审的原批次须重新院审、校审。' : '以正式任务当前状态继续办理；本次未变更任课教师身份。') : '尚未读到与本次调整一致的正式记录，请刷新来源批次核对。' }
      } catch (error) {
        if (valid()) {
          if (commandPhase && (isDeniedResult(error) || isConflictResult(error) || String(error?.code).startsWith('400') || error?.bizCode === 'VALIDATION_ERROR')) this.pendingAdjustment = null
          this.handleFailure(error, '连接中断，请重新读取正式任务，勿重复调整。')
        }
      }
      finally { form.submitting = false }
    },
    async queryPendingAdjustment() {
      if (!this.pendingAdjustment || this.adjust.submitting || this.loading) return
      const pending = this.pendingAdjustment, context = this.ctx
      this.adjust.submitting = true
      try {
        const res = await academicAffairsApi.listAllTasks({ taskId: pending.taskId, batchId: pending.batchId, page: 1, pageSize: 1 })
        if (this.disposed || context !== this.ctx || pending !== this.pendingAdjustment) return
        if (res.code !== 0) { this.handleFailure(res, '原调整结果查询失败'); return }
        const row = res.data?.list?.find(item => String(item.taskId) === String(pending.taskId))
        const fields = ['teacherKey', 'weeklyHours', 'totalHours', 'startWeek', 'endWeek', 'expectedStudents']
        const confirmed = row && fields.every(key => pending.body[key] === undefined || String(row[key]) === String(pending.body[key]))
        this.receipt = { object: pending.object, status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, next: confirmed ? '以正式状态继续办理；换教师后需本人确认及原批次复核。' : '尚未读到一致的正式结果，请联系学院核对；不会重复提交。' }
        if (confirmed) { this.pendingAdjustment = null; this.adjust.visible = false; await this.load() }
      } catch (error) { if (context === this.ctx) this.handleFailure(error, '原调整结果查询失败') }
      finally { if (context === this.ctx) this.adjust.submitting = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) { this.revision++; this.loading = false; this.all = []; this.receipt = null; this.adjust = { visible: false, submitting: false } }
      else if (isConflictResult(result)) this.receipt = { object: [this.adjust.courseName, this.adjust.teachingClassName].filter(Boolean).join(' · ') || '教学任务', status: '数据已变化，保留输入', pending: true, next: '核对当前正式任课关系、周次与下游引用；已有课表时从排课变更流程办理。' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/teaching-task-workspace.css';
.task-adjust-heading { margin-bottom: 18px; }
.task-adjust-heading h3 { margin-bottom: 6px; }
.task-adjust-heading p { margin: 0; color: var(--gray-600); }
.task-adjust-layout { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(260px, 1fr); gap: 22px; align-items: start; }
.task-adjust-impact { padding: 16px; background: var(--primary-50, #f0f5ff); border-radius: 8px; }
.task-adjust-impact ol { padding-left: 22px; line-height: 2; }
.task-adjust-error { color: var(--danger-600, #c43232); margin: 6px 0; }
@media (max-width: 1100px) { .task-adjust-layout { grid-template-columns: minmax(0, 1fr); } }
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; min-width: 220px; }
.aa-adjust-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-adjust-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 10px; }
.aa-req { color: var(--danger-600, #d54941); margin-left: 2px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; }
</style>
