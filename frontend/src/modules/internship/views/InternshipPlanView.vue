<template>
  <ModulePageShell title="实习计划书" subtitle="批次计划编制 · 任务清单 · 发布下发 · 学生确认台账"
    role-name="实习管理员 / 指导教师" :data-scope-name="scopeHint">
    <div class="bar">
      <AppSelect v-model="batchId" :options="batchOptions" placeholder="选择实习批次" @change="onBatchChange" />
      <AppButton v-if="batchId && canEdit" variant="primary" :loading="publishing" @click="publish">发布并下发</AppButton>
    </div>

    <div v-if="!batchId" class="state">请先选择实习批次</div>
    <div v-else-if="loading" class="state">加载中…</div>
    <div v-else class="layout">
      <div class="grid">
        <section class="card">
          <h3 class="card__title">计划编制</h3>
          <AppFormItem label="计划标题" required>
            <AppTextInput v-model="form.title" :disabled="!canEdit" />
          </AppFormItem>
          <AppFormItem label="实习目标">
            <AppTextarea v-model="form.objectives" :rows="3" :disabled="!canEdit" />
          </AppFormItem>
          <AppFormItem label="计划正文" required>
            <AppTextarea v-model="form.content" :rows="8" placeholder="不少于 20 字" :disabled="!canEdit" />
          </AppFormItem>
          <AppButton v-if="canEdit" variant="secondary" :loading="saving" @click="save">保存草稿</AppButton>
          <p v-if="plan" class="hint">状态：{{ plan.statusLabel }} · {{ plan.publishedAt || '未发布' }}</p>
          <AppInlineAlert v-else-if="canEdit" type="info" class="hint">尚未保存计划，填写后请先保存草稿</AppInlineAlert>
        </section>
        <section class="card">
          <h3 class="card__title">学生确认台账</h3>
          <AppQuickFilterChips v-model="ackStatus" :options="ackOptions" allow-clear @change="loadAcks" />
          <DataTable :columns="ackCols" :rows="acks" row-key="id" :loading="ackLoading"
            :pagination="ackPagination" @page-change="onAckPage" />
        </section>
      </div>

      <section ref="taskSection" class="card card--tasks" :class="{ 'is-focus': taskPanelFocus }">
        <div class="card__head">
          <h3 class="card__title">实习任务清单</h3>
          <span class="card__sub">批次下发后学生可在学生端查看任务清单</span>
        </div>

        <template v-if="canEdit">
          <p v-if="!tasks.length" class="state state--inline">暂无任务，点击下方添加（可选，建议 3～10 项）</p>
          <div v-for="(task, idx) in tasks" :key="task._key" class="task-row">
            <div class="task-row__idx">{{ idx + 1 }}</div>
            <div class="task-row__fields">
              <AppFormItem label="任务名称" required>
                <AppTextInput v-model="task.name" placeholder="如：完成岗前安全培训" />
              </AppFormItem>
              <AppFormItem label="完成要求">
                <AppTextarea v-model="task.requirement" :rows="2" placeholder="验收标准、提交物等" />
              </AppFormItem>
              <AppDeadlinePicker v-model="task.deadline" label="截止时间" hint="默认 23:59，可不填" clearable />
            </div>
            <div class="task-row__ops">
              <AppButton variant="ghost" size="sm" :disabled="idx === 0" @click="moveTask(idx, -1)">↑</AppButton>
              <AppButton variant="ghost" size="sm" :disabled="idx === tasks.length - 1" @click="moveTask(idx, 1)">↓</AppButton>
              <AppButton variant="ghost" size="sm" :danger="true" @click="removeTask(idx)">删除</AppButton>
            </div>
          </div>
          <div class="task-actions">
            <AppButton variant="secondary" size="sm" :disabled="tasks.length >= 50" @click="addTask">+ 添加任务</AppButton>
            <AppButton variant="secondary" :loading="saving" @click="save">保存任务与计划</AppButton>
          </div>
        </template>

        <template v-else>
          <DataTable v-if="tasks.length" :columns="taskCols" :rows="taskRows" row-key="sortOrder">
            <template #cell-deadline="{ row }">
              <AppDateDisplay :value="row.deadline" mode="deadline" />
            </template>
            <template #cell-requirement="{ row }">
              <span class="req-text">{{ row.requirement || '—' }}</span>
            </template>
          </DataTable>
          <p v-else class="state state--inline">本批次计划未配置任务清单</p>
        </template>
      </section>

      <section v-if="plan && plan.status === 'PUBLISHED'" ref="progressSection"
        class="card card--progress" :class="{ 'is-focus': progressPanelFocus }">
        <div class="card__head">
          <h3 class="card__title">任务完成度跟踪</h3>
          <span class="card__sub">学生提交 → 指导教师确认 · 支持任务节点完成度跟踪</span>
        </div>
        <div v-if="taskSummary" class="stats">
          <AppMetricCard title="平均完成率" :value="taskSummary.avgRate" unit="%" />
          <AppMetricCard title="待确认" :value="taskSummary.pendingReview" />
          <AppMetricCard title="参与学生" :value="taskSummary.studentCount" />
          <AppMetricCard title="任务项" :value="taskSummary.totalTasks" />
        </div>
        <div class="bar bar--inner">
          <AppSearchBox v-model="progKeyword" placeholder="按姓名/学号搜索" @search="reloadProgress" />
          <AppQuickFilterChips v-model="progStatus" :options="progStatusOptions" allow-clear @change="reloadProgress" />
          <AppSelect v-model="progTaskOrder" :options="progTaskOptions" placeholder="全部任务" allow-clear @change="reloadProgress" />
        </div>
        <DataTable :columns="progCols" :rows="progRows" row-key="id" :loading="progLoading"
          :pagination="progPagination" @page-change="onProgPage">
          <template #cell-status="{ row }">
            <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
          </template>
          <template #cell-studentNote="{ row }">
            <span class="req-text">{{ row.studentNote || '—' }}</span>
          </template>
          <template #cell-actions="{ row }">
            <template v-if="row.status === 'SUBMITTED'">
              <AppButton variant="secondary" size="sm" @click="openReview(row, 'APPROVE')">确认完成</AppButton>
              <AppButton variant="ghost" size="sm" :danger="true" @click="openReview(row, 'REJECT')">退回</AppButton>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </DataTable>
      </section>
    </div>

    <AppConfirmDialog v-model:visible="delCd.visible" title="删除任务"
      :content="delCd.content" :danger="true" confirm-text="删除" @confirm="confirmRemoveTask" />
    <AppConfirmDialog v-model:visible="reviewCd.visible" :title="reviewCd.title" :content="reviewCd.content"
      :danger="reviewCd.danger" :require-reason="reviewCd.requireReason" :submitting="reviewCd.submitting"
      @confirm="onReviewConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppFormItem, AppTextInput, AppTextarea, AppSelect, AppQuickFilterChips,
  AppDeadlinePicker, AppDateDisplay, AppConfirmDialog, AppInlineAlert,
  AppStatusTag, AppSearchBox, AppMetricCard
} from '@/components/common'
import { planApi } from '@/modules/internship/api/plan-insurance.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

let _taskKey = 0
function newTask(src = {}) {
  return {
    _key: ++_taskKey,
    sortOrder: src.sortOrder || 0,
    name: src.name || '',
    requirement: src.requirement || '',
    deadline: src.deadline || ''
  }
}

export default {
  name: 'InternshipPlanView',
  components: {
    ModulePageShell, DataTable, AppButton, AppFormItem, AppTextInput, AppTextarea,
    AppSelect, AppQuickFilterChips, AppDeadlinePicker, AppDateDisplay, AppConfirmDialog,
    AppInlineAlert, AppStatusTag, AppSearchBox, AppMetricCard
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchId: '', batchOptions: [], plan: null, loading: false, saving: false, publishing: false,
      form: { title: '', objectives: '', content: '' },
      tasks: [],
      acks: [], ackLoading: false, ackStatus: '', ackPagination: { page: 1, pageSize: 10, total: 0 },
      ackCols: [
        { key: 'studentName', title: '姓名' }, { key: 'studentNo', title: '学号' },
        { key: 'statusLabel', title: '确认状态' }, { key: 'acknowledgedAt', title: '确认时间' }
      ],
      taskCols: [
        { key: 'sortOrder', title: '序号', width: '56px' },
        { key: 'name', title: '任务名称' },
        { key: 'requirement', title: '完成要求' },
        { key: 'deadline', title: '截止时间', width: '160px' }
      ],
      ackOptions: [{ label: '待确认', value: 'PENDING' }, { label: '已确认', value: 'ACKNOWLEDGED' }],
      scopeHint: '管理员全校；指导教师仅本人指导学生',
      taskPanelFocus: false,
      progressPanelFocus: false,
      delCd: { visible: false, content: '', idx: -1 },
      taskSummary: null,
      progRows: [], progLoading: false, progKeyword: '', progStatus: 'SUBMITTED',
      progTaskOrder: '', progPage: 1, progPageSize: 10, progTotal: 0,
      progCols: [
        { key: 'studentName', title: '姓名' }, { key: 'studentNo', title: '学号' },
        { key: 'taskName', title: '任务' }, { key: 'status', title: '状态', width: '100px' },
        { key: 'studentNote', title: '完成说明' }, { key: 'submittedAt', title: '提交时间', width: '140px' },
        { key: 'actions', title: '操作', width: '160px' }
      ],
      progStatusOptions: [
        { label: '待确认', value: 'SUBMITTED' }, { label: '已完成', value: 'APPROVED' },
        { label: '已退回', value: 'REJECTED' }, { label: '未开始', value: 'NOT_STARTED' }
      ],
      reviewCd: { visible: false, title: '', content: '', danger: false, requireReason: false, submitting: false },
      pendingReview: null
    }
  },
  computed: {
    canEdit() {
      return !this.plan || this.plan.status === 'DRAFT'
    },
    taskRows() {
      return this.tasks.map((t, i) => ({
        sortOrder: t.sortOrder || i + 1,
        name: t.name,
        requirement: t.requirement,
        deadline: t.deadline
      }))
    },
    progPagination() { return { page: this.progPage, pageSize: this.progPageSize, total: this.progTotal } },
    progTaskOptions() {
      return this.tasks.map((t, i) => ({
        label: `${i + 1}. ${(t.name || '').trim() || '未命名'}`,
        value: String(t.sortOrder || i + 1)
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(v) {
        if (v === 'tasks') this.$nextTick(() => this.focusTaskPanel())
        if (v === 'progress') this.$nextTick(() => this.focusProgressPanel())
      }
    }
  },
  created() { this.loadBatches() },
  methods: {
    focusTaskPanel() {
      this.taskPanelFocus = true
      const el = this.$refs.taskSection
      if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setTimeout(() => { this.taskPanelFocus = false }, 2400)
    },
    focusProgressPanel() {
      this.progressPanelFocus = true
      const el = this.$refs.progressSection
      if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setTimeout(() => { this.progressPanelFocus = false }, 2400)
    },
    hydrateTasks(list) {
      const arr = Array.isArray(list) ? list : []
      this.tasks = arr.length
        ? arr.map((t, i) => newTask({ ...t, sortOrder: t.sortOrder || i + 1 }))
        : []
    },
    async loadBatches() {
      const res = await internshipApi.getBatches({ page: 1, pageSize: 100 })
      if (res.code === 0) {
        this.batchOptions = (res.data.list || []).map((b) => ({ label: b.batchName, value: b.id }))
        if (this.batchOptions.length) { this.batchId = this.batchOptions[0].value; this.onBatchChange() }
      }
    },
    async onBatchChange() {
      if (!this.batchId) return
      this.loading = true
      const res = await planApi.getBatchPlan(this.batchId)
      this.loading = false
      if (res.code === 0 && res.data) {
        this.plan = res.data
        this.form = { title: res.data.title, objectives: res.data.objectives, content: res.data.content }
        this.hydrateTasks(res.data.tasks)
      } else {
        this.plan = null
        this.form = { title: '', objectives: '', content: '' }
        this.tasks = []
      }
      this.loadAcks()
      this.loadProgressSummary()
      this.reloadProgress()
      const panel = this.$route.query.panel
      if (panel === 'tasks') this.$nextTick(() => this.focusTaskPanel())
      if (panel === 'progress') this.$nextTick(() => this.focusProgressPanel())
    },
    buildTasksPayload() {
      return this.tasks
        .map((t, i) => ({
          sortOrder: i + 1,
          name: (t.name || '').trim(),
          requirement: (t.requirement || '').trim(),
          deadline: (t.deadline || '').trim() || null
        }))
        .filter((t) => t.name || t.requirement || t.deadline)
    },
    validateTasks() {
      for (let i = 0; i < this.tasks.length; i++) {
        const t = this.tasks[i]
        const hasAny = (t.name || '').trim() || (t.requirement || '').trim() || (t.deadline || '').trim()
        if (hasAny && (t.name || '').trim().length < 2) {
          toast.error(`任务 ${i + 1} 名称至少 2 字`)
          return false
        }
      }
      return true
    },
    addTask() {
      if (this.tasks.length >= 50) return toast.warning('任务清单最多 50 条')
      this.tasks.push(newTask({ sortOrder: this.tasks.length + 1 }))
    },
    removeTask(idx) {
      const name = (this.tasks[idx]?.name || '').trim() || `任务 ${idx + 1}`
      this.delCd = { visible: true, content: `确认删除「${name}」？`, idx }
    },
    confirmRemoveTask() {
      if (this.delCd.idx >= 0) this.tasks.splice(this.delCd.idx, 1)
      this.delCd.visible = false
    },
    moveTask(idx, delta) {
      const next = idx + delta
      if (next < 0 || next >= this.tasks.length) return
      const arr = [...this.tasks]
      ;[arr[idx], arr[next]] = [arr[next], arr[idx]]
      this.tasks = arr
    },
    async save() {
      if (!this.validateTasks()) return
      this.saving = true
      const res = await planApi.saveBatchPlan(this.batchId, { ...this.form, tasks: this.buildTasksPayload() })
      this.saving = false
      if (res.code !== 0) return toast.error(res.message)
      toast.success('计划与任务已保存')
      this.onBatchChange()
    },
    async publish() {
      if (!this.plan) return toast.warning('请先保存计划草稿')
      this.publishing = true
      const res = await planApi.publishBatchPlan(this.batchId)
      this.publishing = false
      if (res.code !== 0) return toast.error(res.message)
      toast.success(`已发布，待确认 ${res.data.ackCount || 0} 人`)
      this.onBatchChange()
    },
    onAckPage(p) { this.ackPagination.page = p; this.loadAcks() },
    async loadAcks() {
      if (!this.batchId) return
      this.ackLoading = true
      const res = await planApi.getPlanAcks({
        batchId: this.batchId, status: this.ackStatus,
        page: this.ackPagination.page, pageSize: this.ackPagination.pageSize
      })
      this.ackLoading = false
      if (res.code === 0) {
        this.acks = res.data.list
        this.ackPagination.total = res.data.total
      }
    },
    async loadProgressSummary() {
      if (!this.batchId || !this.plan || this.plan.status !== 'PUBLISHED') {
        this.taskSummary = null
        return
      }
      const res = await planApi.getTaskSummary(this.batchId)
      if (res.code === 0) this.taskSummary = res.data
    },
    reloadProgress() { this.progPage = 1; this.loadProgress() },
    onProgPage(p) { this.progPage = p; this.loadProgress() },
    async loadProgress() {
      if (!this.batchId || !this.plan || this.plan.status !== 'PUBLISHED') {
        this.progRows = []
        return
      }
      this.progLoading = true
      const params = {
        batchId: this.batchId, page: this.progPage, pageSize: this.progPageSize, keyword: this.progKeyword
      }
      if (this.progStatus) params.status = this.progStatus
      if (this.progTaskOrder) params.taskSortOrder = Number(this.progTaskOrder)
      const res = await planApi.getTaskProgress(params)
      this.progLoading = false
      if (res.code === 0) {
        this.progRows = res.data.list
        this.progTotal = res.data.total
      }
    },
    openReview(row, action) {
      this.pendingReview = { id: row.id, action }
      const ap = action === 'APPROVE'
      this.reviewCd = {
        visible: true,
        title: ap ? '确认任务完成' : '退回任务完成',
        content: `${ap ? '确认' : '退回'}「${row.studentName}」的「${row.taskName}」`,
        danger: !ap, requireReason: !ap, submitting: false
      }
    },
    async onReviewConfirm({ reason }) {
      this.reviewCd.submitting = true
      const res = await planApi.reviewTaskProgress(this.pendingReview.id, {
        action: this.pendingReview.action, comment: reason || ''
      })
      this.reviewCd.submitting = false
      if (res.code !== 0) return toast.error(res.message)
      this.reviewCd.visible = false
      toast.success('批阅成功')
      this.loadProgressSummary()
      this.loadProgress()
    }
  }
}
</script>

<style scoped>
.bar { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
.layout { display: flex; flex-direction: column; gap: var(--space-4); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.card { background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: var(--space-4); }
.card--tasks.is-focus { outline: 2px solid var(--primary-500); outline-offset: 2px; }
.card--progress.is-focus { outline: 2px solid var(--primary-500); outline-offset: 2px; }
.stats { display: flex; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-3); }
.stats > * { flex: 1 1 160px; }
.bar--inner { margin-bottom: var(--space-3); }
.muted { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.card__head { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); margin-bottom: var(--space-3); }
.card__title { margin: 0; font-size: var(--font-size-md); }
.card__sub { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); }
.state--inline { padding: var(--space-3) 0; text-align: left; }
.hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); }
.task-row { display: grid; grid-template-columns: 32px 1fr auto; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px dashed var(--border-light); align-items: start; }
.task-row__idx { font-weight: 600; color: var(--text-secondary); padding-top: var(--space-2); text-align: center; }
.task-row__ops { display: flex; flex-direction: column; gap: var(--space-1); padding-top: var(--space-1); }
.task-actions { display: flex; gap: var(--space-3); margin-top: var(--space-3); flex-wrap: wrap; }
.req-text { white-space: pre-wrap; font-size: var(--font-size-sm); color: var(--text-secondary); }
@media (max-width: 960px) {
  .grid { grid-template-columns: 1fr; }
  .task-row { grid-template-columns: 1fr; }
  .task-row__idx { text-align: left; }
  .task-row__ops { flex-direction: row; }
}
</style>
