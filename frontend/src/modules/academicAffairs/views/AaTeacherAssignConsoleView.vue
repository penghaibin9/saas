<template>
  <ModulePageShell
    title="任课教师分配"
    subtitle="从真实教师目录分配并交教师确认"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton v-if="primaryRow?.batchId" @click="openBatch(primaryRow)">来源批次</AppButton>
      <AppButton variant="primary" :disabled="!primaryRow || !canAssign(primaryRow)" @click="openAssign(primaryRow)">分配当前任务</AppButton>
    </template>
    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AaObjectContext v-if="batchId" name="教学任务批次" :identity="`批次 #${batchId}`" source="从来源批次进入的派师队列" />
      <AaTeachingTaskObjectBar
        v-if="primaryRow"
        :name="`${primaryRow.courseName || '课程'} · ${primaryRow.teachingClassName || '教学班待生成'}`"
        :identity="`教学任务 #${primaryRow.taskId} · 批次 #${primaryRow.batchId}`"
        source="来源：已发布培养方案生成的正式教学任务；教师姓名仅用于展示，权限按稳定工号绑定。"
        :status="statusLabel(primaryRow.status)"
        owner="学院教务 / 任课教师"
        next-owner="任课教师确认岗 → 学院核对岗 → 排课岗"
      />
      <AaTeachingTaskStageRail :current="2" current-note="当前派师工作区" />
      <div class="aa-filter">
        <label class="aa-filter__item">状态
          <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="" class="aa-select" @change="changeFilter" />
        </label>
        <AppButton :loading="loading" @click="load">刷新</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无待处理的教学任务"
                 description="请先在「教学任务生成」按学期生成应开课程" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="taskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName || row.courseCode }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-batch="{ row }"><button class="mp-link" @click="openBatch(row)">批次 #{{ row.batchId }}</button></template>
        <template #cell-teacher="{ row }">
          <span v-if="row.teacherName">{{ row.teacherName }}</span>
          <span v-else class="mp-cell-sub">未分配</span>
        </template>
        <template #cell-hours="{ row }">周 {{ row.weeklyHours ?? '—' }} · 计 {{ row.expectedStudents ?? '—' }} 人</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div v-if="row.rejectReason" class="mp-cell-sub is-danger">退回：{{ row.rejectReason }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="canAssign(row)" class="mp-link" :disabled="assign.submitting" @click="openAssign(row)">{{ row.teacherKey ? '改派' : '分配' }}</button>
          <span v-else class="mp-cell-sub">{{ row.status === 'TEACHER_CONFIRMED' || row.status === 'READY' ? '已确认，需走任务调整' : '当前只读' }}</span>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="assign.visible"
      title="分配授课教师"
      type="primary"
      confirm-text="确认分配"
      :submitting="assign.submitting"
      @confirm="doAssign"
    >
      <AaObjectContext :name="assign.courseName" :identity="`任务 #${assign.taskId} · 批次 #${assign.batchId}`" :source="assign.teachingClassName" />
      <div class="aa-assign-form">
        <label>任课教师<AppTeacherPicker v-model="assign.teacherKey" :query="teacherKeyQuery" placeholder="选择任课教师" @change="onTeacherPicked" /></label>
        <label>周学时<input v-model.number="assign.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>预计人数<input v-model.number="assign.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
      <p class="mp-cell-sub">以正式教师工号绑定授课关系；提交前重新核对批次，分配后等待教师本人确认。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 任课教师分配（/admin/academic-affairs/teaching-tasks/assign）：跨批次工作队列。
 * GET /academic-affairs/teaching-tasks（跨批次）+ POST /teaching-tasks/{taskId}/assign。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppSelect, AppTeacherPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { teachingTaskWorkbenchApi } from '../api/teaching-task-workbench.api'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import AaTeachingTaskObjectBar from '../components/teaching-tasks/AaTeachingTaskObjectBar.vue'
import AaObjectContext from '../components/parallel-a/AaObjectContext.vue'
import { readTaskPages } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTeacherAssignConsoleView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppConfirmDialog, AppSelect, AppTeacherPicker, AaOperationReceipt, AaObjectContext, AaTeachingTaskStageRail, AaTeachingTaskObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], filterStatus: '', teacherKeyQuery: { valueField: 'loginName' }, revision: 0, receipt: null,
      statusOptions: [
        { value: '', label: '全部（默认按未完成分配优先）' },
        { value: 'PENDING_ASSIGN', label: '待分配' },
        { value: 'REJECTED_BY_TEACHER', label: '教师退回' },
        { value: 'ASSIGNED', label: '已分配（待教师确认）' },
        { value: 'TEACHER_CONFIRMED', label: '教师已确认' }
      ],
      pagination: { page: 1, pageSize: 20, total: 0 },
      assign: { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '', weeklyHours: null, expectedStudents: null },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'batch', title: '批次' },
        { key: 'teacher', title: '授课教师' },
        { key: 'hours', title: '学时 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    primaryRow() { return this.rows[0] || null },
    batchId() { return String(this.$route.query.batchId || '') },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.manage') }
  },
  watch: {
    batchId() { this.assign.visible = false; this.receipt = null; this.pagination.page = 1; this.load() },
    ctx() { this.assign = { visible: false, submitting: false }; this.receipt = null; this.pagination.page = 1; this.load() }
  },
  created() { this.load() },
  beforeUnmount() { this.revision++; this.disposed = true },
  methods: {
    canAssign(row) { return this.canManage && ['PENDING_ASSIGN', 'ASSIGNED', 'REJECTED_BY_TEACHER'].includes(row.status) },
    changeFilter() { this.pagination.page = 1; this.load() },
    openBatch(row) { this.$router.push({ path: `/admin/academic-affairs/teaching-tasks/${row.batchId}`, query: { returnTo: this.$route.fullPath } }) },
    onTeacherPicked(value, items) {
      this.assign.teacherKey = value || ''
      this.assign.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || (s ? '状态待确认' : '') },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async load() {
      const revision = ++this.revision
      this.loading = true
      this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.listAllTasks({
          batchId: this.batchId || undefined, status: this.filterStatus || undefined,
          page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        if (revision !== this.revision) return
        if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
        else this.handleFailure(res, '派师队列读取失败')
      } catch (error) { if (revision === this.revision) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (revision === this.revision) this.loading = false }
    },
    openAssign(row) {
      if (!this.canAssign(row) || this.assign.submitting || this.loading) return
      this.assign = { visible: true, submitting: false, taskId: row.taskId, batchId: row.batchId, courseName: row.courseName, teachingClassName: row.teachingClassName, teacherName: row.teacherName || '',
                      teacherKey: row.teacherKey || '', weeklyHours: row.weeklyHours, expectedStudents: row.expectedStudents }
    },
    handleFailure(result, fallback) {
      const message = result?.message || fallback
      if (isDeniedResult(result)) {
        this.revision++; this.loading = false; this.rows = []; this.pagination.total = 0; this.receipt = null
        this.assign = { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '' }
        this.error = `${message}；已清除先前内容。`
      } else {
        this.error = message
        if (isConflictResult(result)) this.receipt = { title: '重新核对派师', object: `任务 #${this.assign.taskId}`, status: '事实已变化，保留输入', pending: true, next: '请刷新来源批次后重新核对，不会自动重提。' }
      }
    },
    async doAssign() {
      const form = this.assign
      if (!this.canManage || form.submitting || !form.taskId || !form.batchId) return
      if (!form.teacherKey || !form.teacherName) { toast.error('请选择带正式工号的任课教师'); return }
      const scope = this.batchId
      const teacherKey = form.teacherKey
      form.submitting = true
      const context = this.ctx
      const current = () => !this.disposed && scope === this.batchId && this.assign === form && context === this.ctx
      const object = `${form.courseName || '教学任务'} · #${form.taskId}`
      try {
        const batch = await teachingTaskWorkbenchApi.getBatch(form.batchId)
        if (!current()) return
        if (batch.code !== 0) { this.handleFailure(batch, '批次核对失败，尚未提交。'); return }
        if (!batch.data?.actions?.canAssign) { this.handleFailure({ code: 409001, message: '批次已不允许派师，请核对当前状态。' }); return }
        const result = await academicAffairsApi.assignTeacher(form.taskId, {
          teacherName: form.teacherName, teacherKey, weeklyHours: form.weeklyHours ?? undefined, expectedStudents: form.expectedStudents ?? undefined
        })
        if (!current()) return
        if (result.code !== 0) { this.handleFailure(result, '分配失败'); return }
        const readback = await readTaskPages(page => academicAffairsApi.getBatchTasks(form.batchId, page), current)
        if (!current()) return
        if (readback?.code !== 0) {
          this.receipt = { object, status: '结果待确认', pending: true, next: '未能完整读取正式任务，请刷新来源批次核对，不要重复分配。' }
          this.handleFailure(readback, '正式任务回读失败'); return
        }
        const row = readback.data.list.find(item => String(item.taskId) === String(form.taskId))
        const confirmed = row?.teacherKey === teacherKey && ['ASSIGNED', 'TEACHER_CONFIRMED', 'READY'].includes(row.status)
        form.visible = false
        await this.load()
        if (!current() || this.error) return
        this.receipt = { object, status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, next: confirmed ? '由任课教师本人确认，之后交学院和教务核对。' : '正式记录尚未反映本次分配，请打开来源批次核对。' }
      } catch (error) {
        if (current()) { this.receipt = { object, status: '结果待确认', pending: true, next: '请重新读取来源批次，不要重复提交。' }; this.handleFailure(error, '连接中断，请核对正式任务。') }
      } finally { form.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { min-width: 220px; }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.mp-cell-sub.is-danger { color: var(--danger-600, #d54941); }
</style>
