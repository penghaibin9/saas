<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-link" @click="$router.push('/admin/internship/plans')">任务与计划</button>
      <AppExportButton :export-fn="exportFn" :has-permission="canExport">{{ exportLabel }}</AppExportButton>
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />
      <!-- 报告类型切换（原「日报批阅 / 月报批阅 / 实习总结」独立菜单收口为页内切换） -->
      <div class="mp-tabs">
        <button v-for="t in typeTabs" :key="t.value" class="mp-tab" :class="{ 'is-active': reportTypeKey === t.value }" @click="switchType(t.value)">
          {{ t.label }}
        </button>
      </div>
      <div class="mp-tabs">
        <button v-for="t in activeTabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" description="可切换页签或调整筛选条件" />
      <DataTable
        v-else
        :columns="activeColumns"
        :rows="rows"
        row-key="id"
        :selectable="!isProcessReport"
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template v-if="!isProcessReport" #batch-actions>
          <AppPermissionButton
            code="internship.report.review"
            variant="secondary"
            size="sm"
            :allowed="canBatchApprove"
            :disabled="!selected.length || batchHasRisk || batchSubmitting"
            :loading="batchSubmitting"
            :reason="batchApproveReason"
            @click="batchApprove"
          >批量通过</AppPermissionButton>
          <span class="mp-note" title="退回原因必填，需逐篇进入详情填写">批量退回不可用：退回原因必须逐篇填写</span>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · {{ row.enterpriseName }}</div>
        </template>
        <template #cell-version="{ row }">
          <AppStatusTag v-if="row.isResubmit" type="info">{{ row.version }} 重交</AppStatusTag>
          <span v-else>{{ row.version }}</span>
        </template>
        <template #cell-riskFlag="{ row }">
          <AppRiskTag v-if="row.riskFlag" :level="row.riskFlag" label="风险学生" />
          <span v-else class="mp-note">—</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="!isProcessReport && row.status === 'OVERDUE'" class="mp-link" @click="remind(row)">催交</button>
          <button v-else class="mp-link" @click="goDetail(row)">
            {{ row.status === 'PENDING_REVIEW' ? '批阅' : '查看' }}
          </button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 周报批阅列表（/admin/internship/reports）：P12 → T20 → PC 批阅。 */
import {
  ModulePageShell, DataTable,
  LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppStatusTag, AppRiskTag, AppExportButton, AppPermissionButton } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const PANEL_STATUS = {
  all: '',
  review: 'PENDING_REVIEW',
  returned: 'RETURNED',
  overdue: 'OVERDUE'
}

const TYPE_MAP = {
  daily: { label: '日报', reportType: 'DAILY' },
  monthly: { label: '月报', reportType: 'MONTHLY' },
  summary: { label: '实习总结', reportType: 'SUMMARY' }
}

const PROCESS_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'periodKey', title: '周期' },
  { key: 'submitAt', title: '提交时间' },
  { key: 'wordCount', title: '字数' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '80px' }
]

export default {
  name: 'WeeklyReportListView',
  components: { ModulePageShell, DataTable, AppStatusTag, AppRiskTag, AppExportButton, AppPermissionButton, LoadingState, ErrorState, EmptyState, ModuleSummaryStrip },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      batchSubmitting: false,
      filters: { status: 'PENDING_REVIEW' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: 'PENDING_REVIEW', label: '待批阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'RETURNED', label: '已退回' },
        { value: 'OVERDUE', label: '逾期未交' },
        { value: '', label: '全部' }
      ],
      processTabs: [
        { value: 'PENDING_REVIEW', label: '待批阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'RETURNED', label: '已退回' },
        { value: '', label: '全部' }
      ],
      reportTypeKey: '',
      columns: [
        { key: 'student', title: '学生' },
        { key: 'week', title: '周次' },
        { key: 'submitAt', title: '提交时间' },
        { key: 'version', title: '版本' },
        { key: 'wordCount', title: '字数' },
        { key: 'attachments', title: '附件' },
        { key: 'riskFlag', title: '风险标记' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    isProcessReport() {
      return !!TYPE_MAP[this.reportTypeKey]
    },
    typeConfig() {
      return TYPE_MAP[this.reportTypeKey] || null
    },
    pageTitle() {
      return this.isProcessReport ? `${this.typeConfig.label}批阅` : '周报任务批阅'
    },
    pageSubtitle() {
      if (this.isProcessReport) {
        return `查看学生任务和实习报告，连续完成批阅、退回和催交 · 学生端提交${this.typeConfig.label}，教师在此批阅`
      }
      return '查看学生任务和实习报告，连续完成批阅、退回和催交 · 退回原因必填并同步学生端'
    },
    typeTabs() {
      return [
        { value: '', label: '周报' },
        { value: 'daily', label: '日报' },
        { value: 'monthly', label: '月报' },
        { value: 'summary', label: '实习总结' }
      ]
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const cur = this.activeTabs.find((t) => t.value === this.filters.status)
      const label = (this.isProcessReport ? this.typeConfig.label : '周报') + (cur ? ' · ' + cur.label : '')
      return [{ label, value: this.pagination.total, tone: this.filters.status === 'PENDING_REVIEW' && this.pagination.total ? 'warn' : undefined }]
    },
    exportLabel() {
      return this.isProcessReport ? `⬇ 导出${this.typeConfig.label}` : '⬇ 导出周报'
    },
    emptyTitle() {
      return this.isProcessReport ? `当前页签暂无${this.typeConfig.label}` : '当前页签暂无周报'
    },
    activeTabs() {
      return this.isProcessReport ? this.processTabs : this.tabs
    },
    activeColumns() {
      return this.isProcessReport ? PROCESS_COLUMNS : this.columns
    },
    batchHasRisk() {
      return this.rows.some((r) => this.selected.includes(r.id) && r.riskFlag)
    },
    perm() {
      return this.ctx.permissionActions || {}
    },
    canExport() {
      const p = this.perm.exportReports
      return !p || p.allowed
    },
    canBatchApprove() {
      const p = this.perm.batchApproveReports
      return !!p && p.allowed
    },
    batchApproveReason() {
      if (this.batchHasRisk) return '所选含风险学生周报，需逐篇批阅'
      const p = this.perm.batchApproveReports
      if (p && !p.allowed) return p.reason || '无批量通过权限'
      if (!this.selected.length) return '请先勾选待批阅周报'
      return ''
    }
  },
  watch: {
    '$route.query.type': {
      immediate: true,
      handler(type) {
        this.reportTypeKey = (type || '').toString()
        if (this.isProcessReport && this.filters.status === 'OVERDUE') {
          this.filters.status = 'PENDING_REVIEW'
        }
      }
    },
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || (this.isProcessReport ? 'all' : 'review')).toString())
      }
    }
  },
  methods: {
    goDetail(row) {
      if (this.isProcessReport) {
        this.$router.push(`/admin/internship/process-reports/${row.id}`)
      } else {
        this.$router.push(`/admin/internship/reports/${row.id}`)
      }
    },
    applyPanel(panel) {
      const status = Object.prototype.hasOwnProperty.call(PANEL_STATUS, panel) ? PANEL_STATUS[panel] : PANEL_STATUS.review
      this.filters.status = status
      this.pagination.page = 1
      this.selected = []
      this.load()
    },
    switchType(typeKey) {
      const query = { ...this.$route.query }
      if (typeKey) query.type = typeKey
      else delete query.type
      // 切换报告类型时状态页签回到「待批阅」
      query.panel = 'review'
      this.$router.replace({ path: this.$route.path, query })
      this.reportTypeKey = typeKey
      this.applyPanel('review')
    },
    switchTab(v) {
      const panel = Object.keys(PANEL_STATUS).find((k) => PANEL_STATUS[k] === v) || 'all'
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
      } else {
        this.applyPanel(panel)
      }
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    exportFn() {
      if (this.isProcessReport) {
        return internshipApi.exportProcessReports({
          reportType: this.typeConfig.reportType,
          status: this.filters.status
        })
      }
      return internshipApi.exportWeeklyReports({ status: this.filters.status })
    },
    remind(row) {
      if (!row?.id) return
      internshipApi.remindWeeklyReport(row.id).then((res) => {
        if (res.code === 0) {
          const d = res.data || {}
          const tip = d.notified ? '已向学生发送站内催交通知' : '已写催办审计（学生账号未绑定，未发站内信）'
          toast.success(`已向 ${row.studentName} 催交第 ${d.weekNumber || ''} 周周报 · ${tip}`)
        } else {
          toast.error(res.message || '催交失败')
        }
      })
    },
    async batchApprove() {
      if (!this.canBatchApprove || this.batchHasRisk || !this.selected.length) return
      this.batchSubmitting = true
      try {
        const res = await internshipApi.batchReviewWeeklyReports(this.selected, { action: 'APPROVE', comment: '批量通过' })
        if (res.code === 0) {
          const d = res.data || {}
          toast.success(`已通过 ${d.approvedCount || 0} 篇，跳过 ${d.skippedCount || 0} 篇（已写审计）`)
          this.selected = []
          this.load()
        } else {
          toast.error(res.message || '批量通过失败')
        }
      } finally {
        this.batchSubmitting = false
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize }
      const res = this.isProcessReport
        ? await internshipApi.getProcessReports({ ...params, reportType: this.typeConfig.reportType })
        : await internshipApi.getWeeklyReports(params)
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
