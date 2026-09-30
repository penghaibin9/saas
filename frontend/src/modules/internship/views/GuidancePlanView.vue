<template>
  <ModulePageShell title="指导计划" subtitle="对照批次要求查看指导达成情况，及时跟进指导不足的学生。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">导出批次台账</AppExportButton>
    </template>

    <ModuleSummaryStrip v-if="summaryCards.length" :metrics="summaryCards" />
    <div v-if="statsError" class="state is-err" role="alert">{{ statsError }} <button type="button" class="mp-link" @click="loadStats">重试统计</button></div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="搜索学生姓名或学号" @search="reload" />
      <AppQuickFilterChips :model-value="insufficientOnly ? 'INSUFFICIENT' : statusFilter" :options="statusOptions" allow-clear @change="onStatusFilterChange" />
    </div>

    <p v-if="insufficientOnly || statusFilter" class="export-hint">导出包含当前批次及搜索范围内的全部达标状态。</p>
    <div v-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
    <div v-else-if="loading" class="plan-state" role="status">正在加载指导计划…</div>
    <div v-else-if="!rows.length" class="plan-state" role="status">
      <strong>当前范围内暂无学生</strong>
      <p>可切换批次，或调整姓名与达标状态筛选。</p>
      <AppButton v-if="keyword || insufficientOnly || statusFilter" variant="ghost" @click="clearFilters">清空筛选</AppButton>
    </div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="internId"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-studentName="{ row }">
        <div class="student-name">{{ row.studentName }}</div><div class="sub-text">{{ row.studentNo }}</div>
      </template>
      <template #cell-monthCount="{ row }"><span :class="{ 'count-warning': row.monthCount < row.minMonth }">{{ row.monthCount }}</span><span class="sub-text"> / {{ row.minMonth }} 次</span></template>
      <template #cell-termCount="{ row }"><span :class="{ 'count-warning': row.termCount < row.minTerm }">{{ row.termCount }}</span><span class="sub-text"> / {{ row.minTerm }} 次</span></template>
      <template #cell-planStatus="{ row }">
        <AppStatusTag :type="planTone(row.planStatus)">{{ row.planStatusLabel }}</AppStatusTag>
      </template>
      <template #cell-actions="{ row }">
        <AppButton variant="ghost" size="sm" @click="goGuidance(row)">查指导记录</AppButton>
      </template>
    </DataTable>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppExportButton, AppSearchBox, AppQuickFilterChips } from '@/components/common'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'studentName', title: '学生', width: '140px' },
  { key: 'advisorName', title: '指导教师' },
  { key: 'enterpriseName', title: '企业' },
  { key: 'monthCount', title: '本月 / 要求', width: '110px' },
  { key: 'termCount', title: '学期 / 要求', width: '110px' },
  { key: 'nextFollowDate', title: '下次跟进' },
  { key: 'planStatus', title: '计划状态', width: '110px' },
  { key: 'actions', title: '操作', width: '130px' }
]

export default {
  name: 'GuidancePlanView',
  components: { ModulePageShell, ModuleSummaryStrip, DataTable, AppButton, AppStatusTag, AppExportButton, AppSearchBox, AppQuickFilterChips },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', insufficientOnly: false, columns: COLUMNS,
      stats: null, statsError: '', listSequence: 0, statsSequence: 0,
      scopeHint: '指导教师仅本人指导学生；管理员全校',
      statusOptions: [
        { label: '全部', value: '' },
        { label: '指导不足', value: 'INSUFFICIENT' },
        { label: '达标', value: 'OK' },
        { label: '本月不足', value: 'INSUFFICIENT_MONTH' },
        { label: '学期不足', value: 'INSUFFICIENT_TERM' },
        { label: '月/学期均不足', value: 'INSUFFICIENT_BOTH' }
      ]
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    summaryCards() {
      if (!this.stats) return []
      return [
        { label: '在岗学生', value: this.stats.studentCount },
        { label: '人均学期指导', value: this.stats.avgCount },
        { label: `学期少于 ${this.stats.threshold} 次`, value: this.stats.insufficientCount, warn: this.stats.insufficientCount > 0 }
      ]
    }
  },
  mounted() {
    this.applyRouteQuery()
    this.loadStats()
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'() { this.page = 1; this.loadStats(); this.syncQuery() },
    '$route.query': {
      immediate: false,
      deep: true,
      handler() { this.applyRouteQuery(); this.load() }
    }
  },
  methods: {
    applyRouteQuery() {
      const q = this.$route.query || {}
      this.insufficientOnly = q.insufficient === '1' || q.insufficient === 'true'
      this.statusFilter = this.insufficientOnly ? '' : String(q.planStatus || '')
      this.keyword = String(q.keyword || '')
      this.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
    },
    syncQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, page: String(this.page) })
      delete query.keyword; delete query.planStatus; delete query.insufficient
      if (this.keyword.trim()) query.keyword = this.keyword.trim()
      if (this.insufficientOnly) query.insufficient = '1'
      else if (this.statusFilter) query.planStatus = this.statusFilter
      const current = this.$route.query || {}
      const keys = new Set([...Object.keys(current), ...Object.keys(query)])
      if ([...keys].every(key => String(current[key] || '') === String(query[key] || ''))) this.load()
      else this.$router.replace({ query })
    },
    clearFilters() { this.keyword = ''; this.statusFilter = ''; this.insufficientOnly = false; this.reload() },
    planTone(s) {
      if (s === 'OK') return 'success'
      if (s === 'INSUFFICIENT_MONTH') return 'warning'
      return 'danger'
    },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return guidanceVisitApi.exportGuidancePlans({ keyword: this.keyword, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条指导计划（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.syncQuery() },
    onPageChange(p) { this.page = p; this.syncQuery() },
    async loadStats() {
      const sequence = ++this.statsSequence
      const batchId = this.batchStore.selectedBatchId
      this.stats = null; this.statsError = ''
      if (!batchId) return
      const res = await guidanceVisitApi.getGuidanceStats(2, { batchId })
      if (sequence !== this.statsSequence || batchId !== this.batchStore.selectedBatchId) return
      if (res.code !== 0) { this.statsError = res.message || '统计加载失败'; return }
      this.stats = res.data
    },
    async load() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!batchId) { this.loading = false; this.error = '请先选择批次'; return }
      this.loading = true
      this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId }
      if (this.insufficientOnly) params.insufficientOnly = true
      else if (this.statusFilter) params.planStatus = this.statusFilter
      const res = await guidanceVisitApi.getGuidancePlans(params)
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '加载失败'
        this.rows = []
        this.total = 0
        return
      }
      this.rows = res.data.list
      this.total = res.data.total
      const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (this.page > lastPage) { this.page = lastPage; this.syncQuery() }
    },
    goGuidance(row) {
      this.$router.push({ path: '/admin/internship/guidance', query: this.batchStore.withBatchQuery({ panel: 'guidance', keyword: row.studentName }) })
    },
    onStatusFilterChange(value) {
      this.insufficientOnly = value === 'INSUFFICIENT'
      this.statusFilter = this.insufficientOnly ? '' : (value || '')
      this.reload()
    }
  }
}
</script>

<style scoped>
.plan-state { padding: 48px 20px; text-align: center; background: var(--bg-card); border: 1px solid var(--border-light); border-radius: 12px; color: var(--text-secondary); }
.plan-state strong { color: var(--text-primary); font-size: 16px; }
.plan-state p { font-size: 13px; margin: 8px 0 16px; }
.student-name { font-weight: 600; color: var(--text-primary); }
.sub-text, .export-hint { color: var(--text-secondary); font-size: 12px; }
.count-warning { color: var(--warning-700, #b45309); font-weight: 600; }
.export-hint { margin: 0 0 12px; }
.bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.state.is-err { color: var(--danger-600, #dc2626); margin: 12px 0; }
</style>
