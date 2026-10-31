<template>
  <AaTeachingClassDetailView v-if="workspaceMode === 'class-detail'" :ctx="ctx" />
  <AaTeachingClassListView v-else-if="workspaceMode === 'classes'" :ctx="ctx" />
  <ModulePageShell
    v-else
    :title="showGen ? '教学任务生成' : '教学任务批次'"
    :subtitle="showGen ? '重复生成不会产生重复任务，不要手工建立没有来源的教学任务' : '从培养方案生成任务，按批次跟进开课办理'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton @click="openTeachingClasses">教学班与名单</AppButton>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
      <AppButton v-if="canManage" variant="primary" @click="showGen = !showGen">从方案生成任务</AppButton>
    </template>

    <div class="mp-stack task-workspace">
      <AaOperationReceipt :receipt="receipt && { title: '任务生成回执', ...receipt }" />
      <AaTeachingTaskStageRail :current="showGen ? 1 : 0" :steps="offeringSteps" expanded current-note="开课办理流程" />

      <AppSectionCard v-if="showGen && canManage" title="从已发布培养方案生成">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <AppTermEntityPicker v-model="gen.termId" placeholder="选择学期" :disabled="generating" />
          </label>
          <label class="aa-cal-form__item">
            开课责任学院
            <AppCollegePicker v-model="gen.collegeId" placeholder="选择负责开课与学院确认的学院" :disabled="generating" data-scope-hint="按当前授权范围选择开课责任学院" />
          </label>
          <label class="aa-cal-form__item">
            行政班（可选）
            <AppClassPicker v-model="gen.classId" placeholder="选择行政班，仅补生成该班" :disabled="generating || !gen.collegeId" data-scope-hint="请选当前开课学院的行政班；留空按全院生成" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="gen.batchName" class="aa-input" placeholder="选填，如 2026秋教学任务" maxlength="50" :disabled="generating" />
          </label>
          <AppButton variant="primary" :disabled="!gen.termId || !gen.collegeId" :loading="generating" @click="doGenerate">生成并检查</AppButton>
        </div>
        <AppInlineAlert v-if="genError" type="danger" :description="genError" />
        <p class="mp-note">一个批次明确一个开课责任学院，由该学院落实教师与学院确认，再交校教务终审。行政班留空按全院生成；选择班级时仅为该班补生成新任务。无法解析培养方案或年级关系时会说明未生成原因。教学周数以正式校历为准，未维护时不会猜测生成。</p>
      </AppSectionCard>

      <section class="task-batch-filters">
        <label class="task-batch-filters__term" aria-label="学期">
          <AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" clearable @change="applyFilters" />
        </label>
        <label aria-label="批次状态">
          <select v-model="filters.status" class="aa-select" @change="applyFilters">
            <option value="">全部状态</option>
            <option v-for="(label, key) in batchStatuses" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="task-batch-filters__search" aria-label="快速搜索">
          <input v-model.trim="keyword" class="aa-input" placeholder="搜索批次名称" @keyup.enter="applyFilters" />
        </label>
        <AppButton @click="applyFilters">查询</AppButton>
        <ul v-if="!loading && !error" class="aa-stat-strip task-batch-strip" aria-label="批次概况">
          <li v-for="metric in metrics" :key="metric.label" :title="metric.note"><span>{{ metric.short }}</span><b>{{ metric.value }}</b></li>
        </ul>
      </section>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!filteredRows.length" title="没有符合条件的教学任务批次" description="先发布并绑定培养方案，再生成当前学期教学任务" />
      <DataTable v-else :columns="columns" :rows="filteredRows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.batchName || `批次 ${row.batchId}` }}</div>
          <div class="mp-cell-sub">{{ row.termLabel || '学期待核对' }} · 共 {{ row.taskTotal ?? 0 }} 条任务</div>
        </template>
        <template #cell-college="{ row }">{{ row.collegeName || '责任学院待核对' }}</template>
        <template #cell-stage="{ row }"><AppStatusTag :label="stageLabel(row)" :type="statusColor(row.status)" /></template>
        <template #cell-blockers="{ row }">
          <div v-if="row.blockers?.length" class="task-batch-blockers">
            <span v-for="item in row.blockers.slice(0, 3)" :key="item.code">{{ item.message }}</span>
            <small v-if="row.blockers.length > 3">另有 {{ row.blockers.length - 3 }} 类问题</small>
          </div>
          <span v-else class="task-batch-ready">无阻断</span>
        </template>
        <template #cell-next="{ row }">
          <div class="mp-cell-main">{{ row.nextAction?.label || '核对批次状态' }}</div>
          <div v-if="row.blockerCount" class="mp-cell-sub is-warning">共 {{ row.blockerCount }} 项阻断</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openNext(row)">{{ actionLabel(row) }}</button><br /><button class="mp-link mp-cell-sub" @click="openBatch(row)">查看批次</button>
        </template>
      </DataTable>
      <p class="task-workspace__notice">终审通过表示可以进入排课，不表示课表已完成。</p>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppTermEntityPicker, AppCollegePicker, AppClassPicker, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '@/modules/academicAffairs/constants/teaching'
import AaTeachingClassListView from './AaTeachingClassListView.vue'
import AaTeachingClassDetailView from './AaTeachingClassDetailView.vue'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import { teachingTaskWorkbenchApi } from '../api/teaching-task-workbench.api'
import { matchPermission } from '@/config/navPlan'
import { currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext.js'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTaskBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppTermEntityPicker, AppCollegePicker, AppClassPicker, AppInlineAlert, AaTeachingClassListView, AaTeachingClassDetailView, AaOperationReceipt, AaTeachingTaskStageRail },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      offeringSteps: [{ label: '方案生成' }, { label: '任务准备' }, { label: '教师本人确认' }, { label: '学院核对' }, { label: '校教务终审' }, { label: '可进入排课' }],
      loading: true,
      error: '',
      rows: [],
      revision: 0, receipt: null,
      showGen: false,
      generating: false, generateSeq: 0, collegeSeq: 0, genError: '',
      gen: { termId: '', collegeId: '', classId: '', batchName: '' },
      filters: { termId: '', status: '' },
      keyword: '',
      batchStatuses: TASK_BATCH_STATUS,
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batch', title: '批次 / 规模' },
        { key: 'college', title: '开课责任学院' }, { key: 'stage', title: '当前环节', width: '140px' },
        { key: 'blockers', title: '当前阻断' },
        { key: 'next', title: '下一步' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.manage') },
    generationContext() { return JSON.stringify([academicIdentity(currentUserFromToken(), this.ctx), this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    workspaceMode() {
      if (this.$route.query.view !== 'classes') return 'tasks'
      return this.$route.query.teachingClassId ? 'class-detail' : 'classes'
    },
    metrics() {
      const rows = this.rows || []
      const pending = rows.filter(row => ['DRAFT', 'GENERATED'].includes(row.status) && !row.taskTotal).length
      const processing = rows.filter(row => !['APPROVED', 'ARCHIVED'].includes(row.status) && (row.taskTotal > 0 || row.status === 'RETURNED')).length
      const completed = rows.filter(row => ['APPROVED', 'ARCHIVED'].includes(row.status)).length
      return [
        { label: '当前范围批次', short: '共', value: this.pagination.total, note: '当前学期与权限范围内的批次' },
        { label: '本页待启动', short: '本页待启动', value: pending, note: '本页待启动' },
        { label: '本页进行中', short: '本页进行中', value: processing, note: '本页进行中' },
        { label: '本页已完成', short: '本页已完成', value: completed, note: '本页已完成' }
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
    generationContext() { this.revision++; this.generateSeq++; this.collegeSeq++; this.generating = false; this.genError = ''; this.rows = []; this.receipt = null; this.showGen = false; this.gen = { termId: '', collegeId: '', classId: '', batchName: '' }; if (this.workspaceMode === 'tasks') this.load() },
    'gen.collegeId'(next, previous) { if (next !== previous) this.gen.classId = '' },
    showGen(value) { if (value) this.prefillCollege() },
    '$route.query.open'(value) { this.showGen = value === 'generate' },
    workspaceMode(value) {
      if (value === 'tasks' && !this.rows.length) this.load()
    }
  },
  beforeUnmount() { this.revision++; this.generateSeq++; this.collegeSeq++; this.disposed = true },
  methods: {
    stageLabel(row) {
      if (row.status === 'ARCHIVED') return '已归档'
      if (row.status === 'APPROVED') return '开课审核完成'
      if (row.status === 'COLLEGE_CONFIRMED') return '校教务终审'
      if (!['DRAFT', 'RETURNED', 'GENERATED', 'ASSIGNING', 'TEACHER_CONFIRMING', 'TEACHER_CONFIRMED'].includes(row.status)) return TASK_BATCH_STATUS[row.status] || '状态待核对'
      if (row.unassignedCount || row.teacherRejectedCount) return '任务准备'
      if (row.waitingTeacherCount) return '教师本人确认'
      return row.taskTotal ? '学院核对' : '方案生成'
    },
    actionLabel(row) {
      if (row.status === 'APPROVED' && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.schedule.view')) return '进入本学期排课'
      if (['DRAFT', 'RETURNED'].includes(row.status) && (row.unassignedCount || row.teacherRejectedCount) && (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.assign')) return '分配教师'
      if (!row.waitingTeacherCount && !row.blockerCount && ['DRAFT', 'RETURNED', 'COLLEGE_CONFIRMED'].includes(row.status) && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.confirm')) return '核对办理条件'
      return '查看办理进度'
    },
    openNext(row) {
      const label = this.actionLabel(row)
      const query = { batchId: String(row.batchId), termId: String(row.termId), returnTo: this.$route.fullPath }
      if (label === '进入本学期排课') { delete query.batchId; return this.$router.push({ path: '/admin/academic-affairs/schedule', query }) }
      if (label === '分配教师') return this.$router.push({ path: '/admin/academic-affairs/teaching-tasks/assign', query })
      if (label === '核对办理条件') return this.$router.push({ path: '/admin/academic-affairs/teaching-tasks/confirm', query })
      return this.openBatch(row)
    },
    statusColor: taskBatchColor,
    openTeachingClasses() { this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes', termId: this.filters.termId || undefined, returnTo: this.$route.fullPath } }) },
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
    async prefillCollege() {
      if ((this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) !== 'COLLEGE' || this.gen.collegeId || !this.canManage) return
      const seq = ++this.collegeSeq, context = this.generationContext
      const valid = () => !this.disposed && this.showGen && seq === this.collegeSeq && context === this.generationContext
      try {
        const res = await academicAffairsOrgApi.listColleges({ page: 1, pageSize: 2 })
        if (!valid()) return
        if (res.code !== 0 || !Array.isArray(res.data?.list)) throw res
        if (!this.gen.collegeId && res.data.total === 1 && res.data.list.length === 1) {
          const id = res.data.list[0].id ?? res.data.list[0].collegeId
          if (id != null && String(id)) this.gen.collegeId = String(id)
        }
      } catch { if (valid()) this.genError = '责任学院读取失败，请在学院选择器中重新查询后选择。' }
    },
    async doGenerate() {
      if (!this.canManage || this.generating) return
      this.genError = ''
      if (!this.gen.termId || !this.gen.collegeId) { this.genError = '请选择学期与开课责任学院'; return }
      const classId = this.gen.classId == null ? '' : this.gen.classId
      if (classId !== '' && (typeof classId !== 'string' || !/^[1-9]\d*$/.test(classId))) { this.genError = '请重新选择有效行政班'; return }
      this.generating = true
      const termId = String(this.gen.termId), collegeId = String(this.gen.collegeId), context = this.generationContext, seq = ++this.generateSeq
      const valid = () => !this.disposed && seq === this.generateSeq && context === this.generationContext
      this.receipt = { object: `学期编号 ${termId}`, status: '结果待确认', pending: true, next: '生成后查询正式批次；请勿重复提交。' }
      try {
        const res = await academicAffairsApi.generateTaskBatch({ termId, collegeId, batchName: this.gen.batchName || undefined, ...(classId ? { classId } : {}) })
        if (!valid()) return
        if (res.code !== 0) { this.handleFailure(res, '生成失败，请核对培养方案和学期配置'); return }
        const batchId = res.data?.batchId
        if (!batchId) return
        const readback = await teachingTaskWorkbenchApi.getBatch(batchId)
        if (!valid()) return
        if (readback.code !== 0) { this.handleFailure(readback, '生成后正式批次读取失败'); return }
        const batch = readback.data
        const confirmed = String(batch?.termId) === termId && String(batch?.collegeId) === collegeId && String(batch?.batchId) === String(batchId)
        this.receipt = { object: `${batch?.batchName || '教学任务批次'} · #${batchId}`, status: confirmed ? TASK_BATCH_STATUS[batch.status] || '状态待确认' : '结果待确认', pending: !confirmed, time: batch?.generatedAt, next: confirmed ? batch.nextAction?.label || '进入批次核对任务与阻断项，再分配教师。' : '返回批次列表核对，不要重复生成。' }
        if (confirmed) { this.showGen = false; this.gen = { termId: '', collegeId: '', classId: '', batchName: '' }; await this.load() }
      } catch (error) { if (valid()) this.handleFailure(error, '连接中断，请查询学期正式批次，不要重复生成。') }
      finally { if (valid()) this.generating = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) { this.revision++; this.generateSeq++; this.collegeSeq++; this.generating = false; this.loading = false; this.rows = []; this.receipt = null; this.gen = { termId: '', collegeId: '', classId: '', batchName: '' }; this.showGen = false }
      else if (isConflictResult(result)) this.receipt = { object: `学期编号 ${this.gen.termId}`, status: '数据已变化，保留输入', pending: true, next: '核对已发布方案和年级绑定后再生成。' }
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
@import '../styles/teaching-task-workspace.css';
.task-batch-overview { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.task-batch-metric { min-height: 92px; padding: 14px 16px; border: 1px solid var(--gray-200); border-radius: 10px; background: var(--bg-card); box-sizing: border-box; }
.task-batch-metric span, .task-batch-metric small { display: block; color: var(--gray-500); font-size: 12px; }
.task-batch-metric strong { display: block; margin: 7px 0 5px; color: var(--gray-900); font-size: 24px; line-height: 1.15; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--gray-700); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 36px; padding: 0 10px; border: 1px solid var(--gray-300); border-radius: 7px; background: var(--bg-card); color: var(--gray-900); font-size: 13px; box-sizing: border-box; }
.task-batch-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 9px 12px; border: 1px solid var(--gray-200); border-radius: 10px; background: var(--bg-card); }
.task-batch-filters label { display: flex; flex-direction: column; gap: 4px; color: var(--gray-600); font-size: 12px; }
.task-batch-filters__search { flex: 0 1 260px; }
.task-batch-strip { margin-left: auto; }
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
<style>
@import '../styles/page-compact.css';
</style>
