<template>
  <ModulePageShell title="指导计划" subtitle="批次规则 · 月度/学期指导频次 · 下次跟进 · 不足预警"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div v-if="summaryCards.length" class="stats">
      <AppMetricCard v-for="c in summaryCards" :key="c.label" :title="c.label" :value="c.value" :accent="c.warn ? 'warning' : 'primary'" />
    </div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="onStatusFilterChange" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="internId" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-planStatus="{ row }">
        <AppStatusTag :type="planTone(row.planStatus)">{{ row.planStatusLabel }}</AppStatusTag>
      </template>
      <template #cell-actions="{ row }">
        <AppButton variant="ghost" size="sm" @click="goGuidance(row)">查看指导记录</AppButton>
      </template>
    </DataTable>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppExportButton, AppSearchBox, AppQuickFilterChips, AppMetricCard } from '@/components/common'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' },
  { key: 'studentName', title: '姓名' },
  { key: 'advisorName', title: '指导教师' },
  { key: 'enterpriseName', title: '企业' },
  { key: 'minMonth', title: '月最低', width: '72px' },
  { key: 'monthCount', title: '本月次数', width: '80px' },
  { key: 'minTerm', title: '学期最低', width: '80px' },
  { key: 'termCount', title: '学期次数', width: '80px' },
  { key: 'nextFollowDate', title: '下次跟进' },
  { key: 'planStatus', title: '计划状态', width: '110px' },
  { key: 'actions', title: '操作', width: '130px' }
]

export default {
  name: 'GuidancePlanView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppExportButton, AppSearchBox, AppQuickFilterChips, AppMetricCard },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', insufficientOnly: false, columns: COLUMNS,
      stats: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校',
      statusOptions: [
        { label: '达标', value: 'OK' },
        { label: '本月不足', value: 'INSUFFICIENT_MONTH' },
        { label: '学期不足', value: 'INSUFFICIENT_TERM' },
        { label: '月/学期均不足', value: 'INSUFFICIENT_BOTH' }
      ]
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    summaryCards() {
      if (!this.stats) return []
      return [
        { label: '在岗学生', value: this.stats.studentCount },
        { label: '人均指导次数', value: this.stats.avgCount },
        { label: `不足 ${this.stats.threshold} 次`, value: this.stats.insufficientCount, warn: this.stats.insufficientCount > 0 }
      ]
    }
  },
  mounted() {
    this.applyRouteQuery()
    this.loadStats()
    this.load()
  },
  watch: {
    '$route.query': {
      immediate: false,
      deep: true,
      handler() { this.applyRouteQuery(); this.load() }
    }
  },
  methods: {
    applyRouteQuery() {
      const q = this.$route.query || {}
      if (q.insufficient === '1' || q.insufficient === 'true') {
        this.statusFilter = ''
        this.insufficientOnly = true
      } else {
        this.insufficientOnly = false
        if (q.planStatus) this.statusFilter = String(q.planStatus)
      }
      if (q.keyword) this.keyword = String(q.keyword)
    },
    planTone(s) {
      if (s === 'OK') return 'success'
      if (s === 'INSUFFICIENT_MONTH') return 'warning'
      return 'danger'
    },
    exportFn() { return guidanceVisitApi.exportGuidancePlans({ keyword: this.keyword }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条指导计划（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async loadStats() {
      const res = await guidanceVisitApi.getGuidanceStats(2)
      if (res.code === 0) this.stats = res.data
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.insufficientOnly) params.insufficientOnly = true
      else if (this.statusFilter) params.planStatus = this.statusFilter
      const res = await guidanceVisitApi.getGuidancePlans(params)
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '加载失败'
        this.rows = []
        this.total = 0
        return
      }
      this.rows = res.data.list
      this.total = res.data.total
    },
    goGuidance(row) {
      this.$router.push({ path: '/admin/internship/guidance', query: { panel: 'guidance', keyword: row.studentName } })
    },
    onStatusFilterChange() {
      this.insufficientOnly = false
      this.reload()
    }
  }
}
</script>

<style scoped>
.stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.stats > * { flex: 1 1 160px; }
.bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.state.is-err { color: var(--danger-600, #dc2626); margin: 12px 0; }
</style>
