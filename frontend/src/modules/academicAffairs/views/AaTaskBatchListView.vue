<template>
  <AaTeachingClassDetailView v-if="workspaceMode === 'class-detail'" :ctx="ctx" />
  <AaTeachingClassListView v-else-if="workspaceMode === 'classes'" :ctx="ctx" />
  <ModulePageShell
    v-else
    :title="showGen ? '教学任务生成' : '教学任务批次'"
    :subtitle="showGen ? '幂等生成，不手工造无来源教学任务' : '先确认已发布方案和年级绑定，再生成'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton @click="openTeachingClasses">教学班与名单</AppButton>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
      <AppButton v-if="canManage" variant="primary" @click="showGen = !showGen">从方案生成任务</AppButton>
    </template>

    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt && { title: '任务生成回执', ...receipt }" />
      <AaTeachingTaskStageRail v-if="showGen" :current="1" current-note="生成新批次" />
      <section v-if="!loading && !error" class="task-batch-overview">
        <article v-for="metric in metrics" :key="metric.label" class="task-batch-metric">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.note }}</small>
        </article>
      </section>

      <AppSectionCard v-if="showGen && canManage" title="从已发布培养方案生成">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <AppTermEntityPicker v-model="gen.termId" placeholder="选择学期" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="gen.batchName" class="aa-input" placeholder="选填，如 2026秋教学任务" maxlength="50" />
          </label>
          <AppButton variant="primary" :disabled="!gen.termId" :loading="generating" @click="doGenerate">生成并检查</AppButton>
        </div>
        <p class="mp-note">系统只生成当前学期应开的课程；无法解析学期序号、培养方案或年级关系时会明确返回未生成原因，不会猜测生成。</p>
      </AppSectionCard>

      <section class="task-batch-filters">
        <label>学期
          <AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" clearable @change="applyFilters" />
        </label>
        <label>批次状态
          <select v-model="filters.status" class="aa-select" @change="applyFilters">
            <option value="">全部状态</option>
            <option v-for="(label, key) in batchStatuses" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="task-batch-filters__search">快速搜索
          <input v-model.trim="keyword" class="aa-input" placeholder="输入批次名称" @keyup.enter="applyFilters" />
        </label>
        <AppButton @click="applyFilters">查询批次</AppButton>
      </section>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!filteredRows.length" title="没有符合条件的教学任务批次" description="先发布并绑定培养方案，再生成当前学期教学任务" />
      <DataTable v-else :columns="columns" :rows="filteredRows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.batchName || `批次 ${row.batchId}` }}</div>
          <div class="mp-cell-sub">{{ row.termLabel || '学期待核对' }} · 共 {{ row.taskTotal ?? 0 }} 条任务</div>
        </template>
        <template #cell-progress="{ row }">
          <div class="task-progress-line"><span>分配</span><strong>{{ row.assignedRate ?? 0 }}%</strong></div>
          <div class="task-progress"><span :style="{ width: `${row.assignedRate || 0}%` }" /></div>
          <div class="task-progress-line is-secondary"><span>教师确认</span><strong>{{ row.teacherConfirmRate ?? 0 }}%</strong></div>
          <div class="task-progress"><span :style="{ width: `${row.teacherConfirmRate || 0}%` }" /></div>
        </template>
        <template #cell-blockers="{ row }">
          <div v-if="row.blockers?.length" class="task-batch-blockers">
            <span v-for="item in row.blockers.slice(0, 3)" :key="item.code">{{ item.message }}</span>
            <small v-if="row.blockers.length > 3">另有 {{ row.blockers.length - 3 }} 类问题</small>
          </div>
          <span v-else class="task-batch-ready">无阻断</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" :type="statusColor(row.status)" dot />
        </template>
        <template #cell-next="{ row }">
          <div class="mp-cell-main">{{ row.nextAction?.label || '核对批次状态' }}</div>
          <div v-if="row.blockerCount" class="mp-cell-sub is-warning">共 {{ row.blockerCount }} 项阻断</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openBatch(row)">进入工作台</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '@/modules/academicAffairs/constants/teaching'
import AaTeachingClassListView from './AaTeachingClassListView.vue'
import AaTeachingClassDetailView from './AaTeachingClassDetailView.vue'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import { teachingTaskWorkbenchApi } from '../api/teaching-task-workbench.api'
import { matchPermission } from '@/config/navPlan'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTaskBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppTermEntityPicker, AaTeachingClassListView, AaTeachingClassDetailView, AaOperationReceipt, AaTeachingTaskStageRail },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      revision: 0, receipt: null,
      showGen: false,
      generating: false,
      gen: { termId: '', batchName: '' },
      filters: { termId: '', status: '' },
      keyword: '',
      batchStatuses: TASK_BATCH_STATUS,
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batch', title: '批次 / 规模' },
        { key: 'progress', title: '执行进度', width: '190px' },
        { key: 'blockers', title: '当前阻断' },
        { key: 'status', title: '批次状态', width: '130px' },
        { key: 'next', title: '下一步' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.manage') },
    workspaceMode() {
      if (this.$route.query.view !== 'classes') return 'tasks'
      return this.$route.query.teachingClassId ? 'class-detail' : 'classes'
    },
    metrics() {
      const rows = this.rows || []
      const pending = rows.filter(row => ['DRAFT', 'GENERATED'].includes(row.status)).length
      const processing = rows.filter(row => ['ASSIGNING', 'TEACHER_CONFIRMING', 'COLLEGE_CONFIRMED'].includes(row.status)).length
      const completed = rows.filter(row => ['APPROVED', 'ARCHIVED'].includes(row.status)).length
      return [
        { label: '当前范围批次', value: this.pagination.total, note: '按正式学期与权限范围读取' },
        { label: '本页待启动', value: pending, note: '需确认来源方案与生成责任' },
        { label: '本页进行中', value: processing, note: '逐批核对派师与确认节点' },
        { label: '本页已完成', value: completed, note: '可回查原批次及正式任务' }
      ]
    },
    filteredRows() { return this.rows }
  },
  created() {
    this.restoreFilters()
    if (this.$route?.query?.open === 'generate') this.showGen = true
    if (this.workspaceMode === 'tasks') this.load()
  },
  watch: {
    '$route.fullPath'() { this.restoreFilters(); if (this.workspaceMode === 'tasks') this.load() },
    ctx() { this.revision++; this.rows = []; this.receipt = null; this.showGen = false; this.gen = { termId: '', batchName: '' }; if (this.workspaceMode === 'tasks') this.load() },
    '$route.query.open'(value) { this.showGen = value === 'generate' },
    workspaceMode(value) {
      if (value === 'tasks' && !this.rows.length) this.load()
    }
  },
  beforeUnmount() { this.revision++; this.disposed = true },
  methods: {
    statusColor: taskBatchColor,
    openTeachingClasses() { this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes' } }) },
    restoreFilters() {
      const q = this.$route.query
      this.filters.termId = typeof q.termId === 'string' ? q.termId : ''
      this.filters.status = typeof q.status === 'string' ? q.status : ''
      this.keyword = typeof q.keyword === 'string' ? q.keyword : ''
      const page = Number(q.page); this.pagination.page = Number.isInteger(page) && page > 0 && page <= 1000000 ? page : 1
    },
    applyFilters() { return this.onPageChange(1) },
    async onPageChange(page) {
      const before = this.$route.fullPath
      await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: this.filters.termId || undefined, status: this.filters.status || undefined, keyword: this.keyword || undefined, page: String(page) } })
      if (before === this.$route.fullPath) { this.restoreFilters(); return this.load() }
    },
    openBatch(row) {
      this.$router.push({ path: `/admin/academic-affairs/teaching-tasks/${row.batchId}`, query: { returnTo: this.$route.fullPath } })
    },
    async doGenerate() {
      if (!this.canManage || this.generating || !this.gen.termId) return
      this.generating = true
      const termId = this.gen.termId
      this.receipt = { object: `学期 #${termId}`, status: '结果待确认', pending: true, next: '生成后查询正式批次；请勿重复提交。' }
      try {
        const res = await academicAffairsApi.generateTaskBatch({ termId, batchName: this.gen.batchName || undefined })
        if (this.disposed) return
        if (res.code !== 0) { this.handleFailure(res, '生成失败，请核对培养方案和学期配置'); return }
        const batchId = res.data?.batchId
        if (!batchId) return
        const readback = await teachingTaskWorkbenchApi.getBatch(batchId)
        if (this.disposed) return
        if (readback.code !== 0) { this.handleFailure(readback, '生成后正式批次读取失败'); return }
        const batch = readback.data
        const confirmed = String(batch?.termId) === String(termId) && String(batch?.batchId) === String(batchId)
        this.receipt = { object: `${batch?.batchName || '教学任务批次'} · #${batchId}`, status: confirmed ? TASK_BATCH_STATUS[batch.status] || '状态待确认' : '结果待确认', pending: !confirmed, time: batch?.generatedAt, next: confirmed ? batch.nextAction?.label || '进入批次核对任务与阻断项，再分配教师。' : '返回批次列表核对，不要重复生成。' }
        if (confirmed) { this.showGen = false; this.gen = { termId: '', batchName: '' }; await this.load() }
      } catch (error) { if (!this.disposed) this.handleFailure(error, '连接中断，请查询学期正式批次，不要重复生成。') }
      finally { this.generating = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) { this.revision++; this.loading = false; this.rows = []; this.receipt = null; this.gen = { termId: '', batchName: '' }; this.showGen = false }
      else if (isConflictResult(result)) this.receipt = { object: `学期 #${this.gen.termId}`, status: '事实已变化，保留输入', pending: true, next: '核对已发布方案和年级绑定后再生成。' }
    },
    async load() {
      const revision = ++this.revision
      this.loading = true
      this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
      const res = await academicAffairsApi.getTaskBatches({
        termId: this.filters.termId || undefined,
        status: this.filters.status || undefined,
        keyword: this.keyword || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (revision !== this.revision) return
      if (res.code === 0) {
        this.rows = res.data?.list || []
        this.pagination.total = Number(res.data?.total || 0)
      } else this.handleFailure(res, '教学任务批次加载失败')
      } catch (error) { if (revision === this.revision) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (revision === this.revision) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.task-batch-overview { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.task-batch-metric { min-height: 92px; padding: 14px 16px; border: 1px solid var(--gray-200); border-radius: 10px; background: var(--bg-card); box-sizing: border-box; }
.task-batch-metric span, .task-batch-metric small { display: block; color: var(--gray-500); font-size: 12px; }
.task-batch-metric strong { display: block; margin: 7px 0 5px; color: var(--gray-900); font-size: 24px; line-height: 1.15; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--gray-700); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 36px; padding: 0 10px; border: 1px solid var(--gray-300); border-radius: 7px; background: var(--bg-card); color: var(--gray-900); font-size: 13px; box-sizing: border-box; }
.task-batch-filters { display: flex; align-items: flex-end; gap: 10px; padding: 9px 12px; border: 1px solid var(--gray-200); border-radius: 10px; background: var(--bg-card); }
.task-batch-filters label { display: flex; flex-direction: column; gap: 4px; color: var(--gray-600); font-size: 12px; }
.task-batch-filters__search { flex: 1; }
.task-batch-filters__search .aa-input { width: 100%; }
.task-progress-line { display: flex; justify-content: space-between; color: var(--gray-700); font-size: 12px; }
.task-progress-line.is-secondary { margin-top: 8px; }
.task-progress { height: 5px; margin-top: 4px; border-radius: 3px; background: var(--gray-100); overflow: hidden; }
.task-progress span { display: block; height: 100%; border-radius: inherit; background: var(--primary-500); }
.task-batch-blockers { display: flex; flex-direction: column; gap: 4px; }
.task-batch-blockers span { color: var(--warning-700); font-size: 12px; }
.task-batch-blockers small { color: var(--gray-500); }
.task-batch-ready { color: var(--success-700); font-size: 12px; font-weight: 600; }
.mp-cell-sub.is-warning { color: var(--warning-700); }
@media (max-width: 1180px) { .task-batch-overview { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .task-batch-overview { grid-template-columns: 1fr 1fr; } .task-batch-filters { flex-direction: column; align-items: stretch; } }
</style>
