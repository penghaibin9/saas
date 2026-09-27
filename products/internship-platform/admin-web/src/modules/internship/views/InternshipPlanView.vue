<template>
  <ModulePageShell :title="reviewId ? '任务批阅' : '计划任务'" :subtitle="reviewId ? '核对任务要求与学生提交，确认结果或说明修改要求。' : '编制实习计划、下发任务并跟踪学生确认。'"
    role-name="实习管理员 / 指导教师" :data-scope-name="scopeHint">
    <template #actions>
      <AppButton v-if="reviewId" variant="ghost" @click="closeTaskReview">返回完成度台账</AppButton>
      <AppButton v-if="!reviewId && batchId && canEdit" variant="primary" :loading="publishing" :disabled="!plan || dirty || saving || writeConflict" @click="publish">发布并下发</AppButton>
    </template>

    <AppInlineAlert v-if="writeError" type="warning" :title="writeConflict ? '计划已更新，本次操作已暂停' : '操作未完成'" :description="writeError" />
    <p v-if="!reviewId && batchId && canEdit && (!plan || dirty)" class="hint">{{ plan ? '有未保存的修改，请先保存再发布。' : '先填写计划和至少一项任务，保存后即可发布。' }}</p>
    <div v-if="!batchId" class="state">请先选择实习批次</div>
    <div v-else-if="loading" class="state">加载中…</div>
    <ErrorState v-else-if="loadError" :message="loadError" @retry="onBatchChange" />
    <div v-else class="layout">
      <nav v-if="!reviewId" class="plan-nav" aria-label="计划任务工作区">
        <AppButton v-for="item in panels" :key="item.value" :variant="activePanel === item.value ? 'primary' : 'ghost'"
          :aria-current="activePanel === item.value ? 'page' : undefined" @click="selectPanel(item.value)">{{ item.label }}</AppButton>
      </nav>
      <template v-if="activePanel === 'plan' || activePanel === 'acks'">
        <section v-show="activePanel === 'plan'" class="card card--editor">
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
        <section v-show="activePanel === 'acks'" class="card">
          <h3 class="card__title">学生确认台账</h3>
          <AppQuickFilterChips v-model="ackStatus" :options="ackOptions" allow-clear @change="resetAcks" />
          <ErrorState v-if="ackError" :message="ackError" @retry="loadAcks" />
          <DataTable v-else :columns="ackCols" :rows="acks" row-key="id" :loading="ackLoading"
            :pagination="ackPagination" @page-change="onAckPage" />
        </section>
      </template>

      <section v-if="activePanel === 'tasks'" class="card card--tasks">
        <div class="card__head">
          <h3 class="card__title">实习任务清单</h3>
          <span class="card__sub">批次下发后学生可在学生端查看任务清单</span>
        </div>

        <template v-if="canEdit">
          <p v-if="!tasks.length" class="state state--inline">至少添加一项可执行任务，明确完成要求与截止时间。</p>
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

      <section v-if="reviewId" class="card task-review" aria-label="学生任务提交详情">
        <div v-if="progLoading" class="state">正在读取任务提交…</div>
        <ErrorState v-else-if="progError" :message="progError" @retry="loadProgress" />
        <AppInlineAlert v-else-if="!reviewRow" type="warning" title="当前台账中未找到这份任务"
          description="记录可能已更新或不在当前筛选范围，请返回台账重新查找。" />
        <template v-else>
          <div class="card__head">
            <h3 class="card__title">{{ reviewRow.studentName }} · {{ reviewRow.taskName }}</h3>
            <AppStatusTag :status="reviewRow.status">{{ reviewRow.statusLabel }}</AppStatusTag>
          </div>
          <p class="hint">学号 {{ reviewRow.studentNo }} · 提交时间 {{ reviewRow.submittedAt || '尚未提交' }}</p>
          <div class="task-review__columns">
            <section class="review-evidence"><h4>任务要求</h4><p>{{ reviewTask?.requirement || '未填写完成要求' }}</p>
              <AppDateDisplay :value="reviewTask?.deadline" mode="deadline" />
            </section>
            <section class="review-evidence"><h4>学生完成说明</h4><p>{{ reviewRow.studentNote || '未填写完成说明' }}</p>
              <AppButton v-if="reviewRow.evidenceFileId" variant="secondary" @click="previewTaskEvidence">查看提交凭证</AppButton>
              <p v-else class="hint">未提交附件凭证</p>
            </section>
          </div>
          <AppInlineAlert v-if="evidenceError" type="warning" :description="evidenceError" />
          <section v-if="reviewRow.reviewedAt" class="review-evidence"><h4>最近批阅</h4>
            <p>{{ reviewRow.reviewedByName }} · {{ reviewRow.reviewedAt }}</p><p>{{ reviewRow.reviewComment || '未填写意见' }}</p>
          </section>
          <div v-if="canReview && reviewRow.status === 'SUBMITTED'" class="task-review__actions">
            <AppButton variant="primary" @click="openReview(reviewRow, 'APPROVE')">确认完成</AppButton>
            <AppButton variant="secondary" @click="openReview(reviewRow, 'REJECT')">退回修改</AppButton>
          </div>
        </template>
      </section>
      <AppInlineAlert v-if="!reviewId && activePanel === 'progress' && plan?.status !== 'PUBLISHED'" type="info"
        title="计划发布后可跟踪任务完成情况" description="先保存并发布计划，学生提交任务后在这里确认或退回。" />
      <section v-if="!reviewId && activePanel === 'progress' && plan?.status === 'PUBLISHED'" class="card card--progress">
        <div class="card__head">
          <h3 class="card__title">任务完成度跟踪</h3>
          <span class="card__sub">学生提交 → 指导教师确认 · 支持任务节点完成度跟踪</span>
        </div>
        <AppInlineAlert v-if="summaryError" type="warning" :description="summaryError" />
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
        <ErrorState v-if="progError" :message="progError" @retry="loadProgress" />
        <DataTable v-else :columns="progCols" :rows="progRows" row-key="id" :loading="progLoading"
          :pagination="progPagination" @page-change="onProgPage">
          <template #cell-status="{ row }">
            <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
          </template>
          <template #cell-studentNote="{ row }">
            <span class="req-text">{{ row.studentNote || '—' }}</span>
          </template>
          <template #cell-actions="{ row }">
            <AppButton variant="secondary" size="sm" @click="openTaskReview(row)">{{ row.status === 'SUBMITTED' && canReview ? '查看并批阅' : '查看提交' }}</AppButton>
          </template>
        </DataTable>
      </section>
    </div>

    <AppConfirmDialog v-model:visible="delCd.visible" title="删除任务"
      :content="delCd.content" :danger="true" confirm-text="删除" @confirm="confirmRemoveTask" />
    <AppConfirmDialog v-model:visible="reviewCd.visible" :title="reviewCd.title" :content="reviewCd.content"
      :danger="reviewCd.danger" :require-reason="reviewCd.requireReason" :submitting="reviewCd.submitting"
      :confirm-text="pendingReview?.action === 'APPROVE' ? '确认完成' : '退回修改'" :confirm-disabled="reviewConflict"
      @confirm="onReviewConfirm">
      <div v-if="pendingReview" class="review-evidence">
        <strong>学生完成说明</strong>
        <p>{{ pendingReview.studentNote || '未填写完成说明' }}</p>
      </div>
      <AppInlineAlert v-if="reviewError" type="warning" :description="reviewError" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppFormItem, AppTextInput, AppTextarea, AppSelect, AppQuickFilterChips,
  AppDeadlinePicker, AppDateDisplay, AppConfirmDialog, AppInlineAlert,
  AppStatusTag, AppSearchBox, AppMetricCard
} from '@/components/common'
import { planApi } from '@/modules/internship/api/plan-insurance.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { fileSdk } from '@/services/file/fileSdk'
import { isConflict } from '@/modules/internship/composables/conflictGuard'
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
    ModulePageShell, DataTable, ErrorState, AppButton, AppFormItem, AppTextInput, AppTextarea,
    AppSelect, AppQuickFilterChips, AppDeadlinePicker, AppDateDisplay, AppConfirmDialog,
    AppInlineAlert, AppStatusTag, AppSearchBox, AppMetricCard
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      plan: null, savedSnapshot: '', writeError: '', writeConflict: false, loadError: '', loadSequence: 0, loading: false, saving: false, publishing: false,
      form: { title: '', objectives: '', content: '' },
      tasks: [],
      acks: [], ackError: '', ackSequence: 0, ackLoading: false, ackStatus: '', ackPagination: { page: 1, pageSize: 10, total: 0 },
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
      panels: [{ value: 'plan', label: '计划编制' }, { value: 'tasks', label: '任务清单' }, { value: 'acks', label: '学生确认' }, { value: 'progress', label: '完成度跟踪' }],
      delCd: { visible: false, content: '', idx: -1 },
      taskSummary: null, summaryError: '', summarySequence: 0,
      progRows: [], progError: '', progSequence: 0, progLoading: false, progKeyword: '', progStatus: 'SUBMITTED',
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
      evidenceError: '', pendingReview: null, reviewError: '', reviewConflict: false
    }
  },
  computed: {
    reviewId() { return this.$route.query.reviewId == null ? '' : String(this.$route.query.reviewId) },
    reviewRow() { return this.progRows.find(row => String(row.id) === this.reviewId) || null },
    reviewTask() { return this.tasks.find(task => Number(task.sortOrder) === Number(this.reviewRow?.taskSortOrder)) || null },
    canReview() { return canCode(this.ctx, 'internship.task.review') },
    draftSnapshot() { return JSON.stringify({ ...this.form, tasks: this.buildTasksPayload() }) },
    dirty() { return this.savedSnapshot !== '' && this.draftSnapshot !== this.savedSnapshot },
    activePanel() { if (this.reviewId) return 'progress'; return this.panels.some(item => item.value === this.$route.query.panel) ? this.$route.query.panel : 'plan' },
    batchStore() { return useInternshipBatchStore() },
    batchId() { return this.batchStore.selectedBatchId },
    canEdit() {
      return !this.loading && !this.loadError && canCode(this.ctx, 'internship.plan.manage') && (!this.plan || this.plan.status === 'DRAFT')
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
    dirty(value) {
      if (typeof window === 'undefined') return
      const guard = window.__SAAS_DIRTY_FORM_GUARD__
      if (value) guard?.markDirty(); else guard?.markSaved()
    },
    '$route.query.reviewId'() { this.pendingReview = null; this.reviewCd.visible = false; this.reviewError = ''; this.reviewConflict = false; this.evidenceError = '' },
    batchId: { immediate: true, handler() { this.onBatchChange() } },
  },
  methods: {
    openTaskReview(row) {
      this.$router.push({ path: this.$route.path, query: { ...this.$route.query, panel: 'progress', reviewId: String(row.id),
        progPage: String(this.progPage), progStatus: this.progStatus, progKeyword: this.progKeyword, progTaskOrder: this.progTaskOrder } })
    },
    closeTaskReview() {
      const query = { ...this.$route.query }; delete query.reviewId
      this.$router.push({ path: this.$route.path, query })
    },
    async previewTaskEvidence() {
      const row = this.reviewRow
      if (!row?.evidenceFileId) return
      this.evidenceError = ''
      try { await fileSdk.preview(String(row.evidenceFileId)) }
      catch (error) { if (this.reviewRow === row) this.evidenceError = error.message || '凭证暂时无法预览，请重试' }
    },
    selectPanel(panel) {
      if (!this.panels.some(item => item.value === panel)) return
      this.$router.push({ path: this.$route.path, query: { ...this.$route.query, panel } })
    },
    hydrateTasks(list) {
      const arr = Array.isArray(list) ? list : []
      this.tasks = arr.length
        ? arr.map((t, i) => newTask({ ...t, sortOrder: t.sortOrder || i + 1 }))
        : []
    },
    async onBatchChange() {
      this.ackSequence++; this.progSequence++; this.summarySequence++
      this.ackError = ''; this.progError = ''; this.summaryError = ''
      this.ackLoading = false; this.progLoading = false
      const sequence = ++this.loadSequence
      const batchId = this.batchId
      this.plan = null; this.form = { title: '', objectives: '', content: '' }; this.tasks = []
      this.acks = []; this.ackPagination.page = 1; this.ackPagination.total = 0
      this.progRows = []; this.progTotal = 0; this.taskSummary = null
      this.pendingReview = null; this.reviewError = ''; this.reviewConflict = false; this.reviewCd.visible = false; this.delCd.visible = false
      this.loadError = ''; this.writeError = ''; this.writeConflict = false; this.savedSnapshot = ''; this.loading = false
      if (!batchId) return
      this.loading = true
      const res = await planApi.getBatchPlan(batchId)
      if (sequence !== this.loadSequence || batchId !== this.batchId) return
      this.loading = false
      if (res.code !== 0) { this.loadError = res.message || '计划加载失败，请重试'; return }
      if (res.data?.id != null) {
        this.plan = res.data
        this.form = { title: res.data.title, objectives: res.data.objectives, content: res.data.content }
        this.hydrateTasks(res.data.tasks)
      } else {
        this.plan = null
        this.form = { title: '', objectives: '', content: '' }
        this.tasks = []
      }
      const query = this.$route.query
      this.progPage = Math.max(1, Number(query.progPage) || 1)
      this.progStatus = query.progStatus ?? 'SUBMITTED'; this.progKeyword = query.progKeyword || ''; this.progTaskOrder = query.progTaskOrder || ''
      this.savedSnapshot = this.draftSnapshot
      this.loadAcks()
      this.loadProgressSummary()
      this.loadProgress()
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
      if (!this.canEdit || this.saving || this.publishing || this.writeConflict) return
      this.writeError = ''
      if (this.form.title.trim().length < 2 || this.form.content.trim().length < 20) {
        this.writeError = '计划标题至少 2 字、正文至少 20 字，请在计划编制中补全。'; return
      }
      if (!this.buildTasksPayload().length) { this.writeError = '请在任务清单中至少添加一项可执行任务。'; return }
      if (!this.validateTasks()) return
      const batchId = this.batchId
      const snapshot = this.draftSnapshot
      this.saving = true
      const res = await planApi.saveBatchPlan(batchId, { ...JSON.parse(snapshot), expectedVersion: this.plan?.version })
      this.saving = false
      if (batchId !== this.batchId) return
      if (res.code !== 0) {
        this.writeConflict = isConflict(res)
        this.writeError = this.writeConflict ? '草稿内容已保留。请复制需要保留的内容，再重新加载计划核对最新版本。' : res.message || '保存失败，请重试'
        return
      }
      this.plan = res.data; this.savedSnapshot = snapshot
      toast.success('计划与任务已保存，可发布下发')
    },
    async publish() {
      if (!this.canEdit || this.saving || this.publishing || this.writeConflict || !this.plan || this.dirty) return
      const batchId = this.batchId
      this.writeError = ''; this.publishing = true
      const res = await planApi.publishBatchPlan(batchId, { expectedVersion: this.plan.version })
      this.publishing = false
      if (batchId !== this.batchId) return
      if (res.code !== 0) {
        this.writeConflict = isConflict(res)
        this.writeError = this.writeConflict ? '计划版本已变化，请重新加载核对后再发布。' : res.message || '发布失败，请重试'
        return
      }
      toast.success(`已发布，待确认 ${res.data.ackCount || 0} 人`)
      this.onBatchChange()
    },
    resetAcks() { this.ackPagination.page = 1; this.loadAcks() },
    onAckPage(p) { this.ackPagination.page = p; this.loadAcks() },
    async loadAcks() {
      const sequence = ++this.ackSequence, batchId = this.batchId
      this.acks = []; this.ackPagination.total = 0; this.ackError = ''; this.ackLoading = false
      if (!batchId) return
      this.ackLoading = true
      const res = await planApi.getPlanAcks({
        batchId: this.batchId, status: this.ackStatus,
        page: this.ackPagination.page, pageSize: this.ackPagination.pageSize
      })
      if (sequence !== this.ackSequence || batchId !== this.batchId) return
      this.ackLoading = false
      if (res.code !== 0) { this.ackError = res.message || '学生确认台账加载失败'; return }
      if (res.code === 0) {
        this.acks = res.data.list
        this.ackPagination.total = res.data.total
      }
    },
    async loadProgressSummary() {
      const sequence = ++this.summarySequence, batchId = this.batchId
      this.taskSummary = null; this.summaryError = ''
      if (!this.batchId || !this.plan || this.plan.status !== 'PUBLISHED') {
        this.taskSummary = null
        return
      }
      const res = await planApi.getTaskSummary(this.batchId)
      if (sequence !== this.summarySequence || batchId !== this.batchId) return
      if (res.code !== 0) { this.summaryError = res.message || '完成度统计加载失败'; return }
      this.taskSummary = res.data
    },
    reloadProgress() { this.progPage = 1; this.loadProgress() },
    onProgPage(p) { this.progPage = p; this.loadProgress() },
    async loadProgress() {
      const sequence = ++this.progSequence, batchId = this.batchId
      this.progRows = []; this.progTotal = 0; this.progError = ''; this.progLoading = false
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
      if (sequence !== this.progSequence || batchId !== this.batchId) return
      this.progLoading = false
      if (res.code !== 0) { this.progError = res.message || '任务完成度加载失败'; return }
      if (res.code === 0) {
        this.progRows = res.data.list
        this.progTotal = res.data.total
      }
    },
    openReview(row, action) {
      if (!this.canReview || this.reviewCd.submitting || row.status !== 'SUBMITTED' || !['APPROVE', 'REJECT'].includes(action)) return
      this.reviewError = ''; this.reviewConflict = false
      this.pendingReview = { id: row.id, action, expectedVersion: row.version, studentNote: row.studentNote }
      const ap = action === 'APPROVE'
      this.reviewCd = {
        visible: true,
        title: ap ? '确认任务完成' : '退回任务完成',
        content: `${ap ? '确认' : '退回'}「${row.studentName}」的「${row.taskName}」`,
        danger: !ap, requireReason: !ap, submitting: false
      }
    },
    async onReviewConfirm({ reason }) {
      if (!this.canReview || !this.pendingReview || this.reviewCd.submitting || this.reviewConflict) return
      if (this.pendingReview.action === 'REJECT' && (reason || '').trim().length < 5) { this.reviewError = '请填写至少 5 字的退回原因，说明需要修改的内容。'; return }
      const pending = this.pendingReview, batchId = this.batchId
      this.reviewError = ''; this.reviewCd.submitting = true
      const res = await planApi.reviewTaskProgress(pending.id, {
        action: pending.action, comment: reason || '', expectedVersion: pending.expectedVersion
      })
      this.reviewCd.submitting = false
      if (this.pendingReview !== pending || batchId !== this.batchId) return
      if (res.code !== 0) {
        this.reviewConflict = isConflict(res)
        this.reviewError = this.reviewConflict ? '任务已更新，本次批阅已暂停。意见已保留，请取消后刷新台账，核对最新提交再办理。' : res.message || '批阅失败，请重试'
        return
      }
      this.reviewCd.visible = false
      toast.success('批阅成功')
      if (this.reviewId) this.closeTaskReview()
      this.loadProgressSummary()
      this.loadProgress()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.task-review__columns { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
.task-review h4 { margin: 0; }
.task-review__actions { display: flex; gap: 12px; border-top: 1px solid var(--border-light); padding-top: 20px; }
@media (max-width: 1000px) { .task-review__columns { grid-template-columns: 1fr; } }
.review-evidence { padding: 14px; border-radius: 8px; background: var(--bg-page, #f7f9fc); margin-bottom: 12px; }
.review-evidence p { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 0; }
.plan-nav { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: 4px; }
.card--editor { max-width: 960px; }
.card--editor .card__title { margin-bottom: 20px; }
.bar { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
.layout { display: flex; flex-direction: column; gap: var(--space-4); }
.card { background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: var(--space-4); }
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
  .task-row { grid-template-columns: 1fr; }
  .task-row__idx { text-align: left; }
  .task-row__ops { flex-direction: row; }
}
</style>
