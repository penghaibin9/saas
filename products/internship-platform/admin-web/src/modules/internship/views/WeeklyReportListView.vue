<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-link" @click="$router.push({ path: '/admin/internship/plans', query: { batchId: batchStore.selectedBatchId } })">任务与计划</button>
      <button class="mp-link" @click="toggleObligations">{{ obligationOpen ? '返回批阅列表' : '应交/未交总览' }}</button>
      <AppExportButton v-if="!obligationOpen" :export-fn="exportFn" :has-permission="canExport">{{ exportLabel }}</AppExportButton>
      <AppExportButton v-else :export-fn="exportObligationsFn" :has-permission="canExport">导出应交/未交</AppExportButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
      <form class="wr-search" @submit.prevent="applySearch">
        <label>学生姓名或学号<input v-model.trim="filterDraft.keyword" placeholder="输入姓名或学号" /></label>
        <template v-if="!obligationOpen">
          <label>提交开始日期<input v-model="filterDraft.startDate" type="date" /></label>
          <label>提交结束日期<input v-model="filterDraft.endDate" type="date" /></label>
        </template>
        <button type="submit" :disabled="batchSubmitting">查询</button>
      </form>
      <p v-if="statisticsError" role="alert">{{ statisticsError }}</p>
      <div v-if="batchFailures.length" class="wr-batch-failures" role="alert">
        <p>以下报告需核对或继续办理，已确认完成的报告不会自动重做：</p>
        <p v-for="item in batchFailures" :key="item.id">{{ item.studentName }} · 报告编号 {{ item.id }}：{{ item.message }}</p>
      </div>

      <section v-if="obligationOpen" class="wr-obligation">
        <div class="wr-obligation__head">
          <div>
            <strong>全批次报告应交 / 实交 / 未交</strong>
            <p>应交数来自当前批次规则；规则为 0 时显示“未配置”，不会伪造完成率。</p>
          </div>
          <div class="wr-obligation__filters">
            <button type="button" class="mp-tab" :class="{ 'is-active': obligationMissingOnly }" @click="setObligationMissing(true)">仅看未交</button>
            <button type="button" class="mp-tab" :class="{ 'is-active': !obligationMissingOnly }" @click="setObligationMissing(false)">全部学生</button>
          </div>
        </div>
        <p v-if="!canRemind" class="mp-cell-sub">当前账号无催交权限，请联系具备报告批阅权限的教师或管理员。</p>
        <ErrorState v-if="obligationError" :description="obligationError" @retry="loadObligations" />
        <LoadingState v-else-if="obligationLoading" />
        <EmptyState v-else-if="!obligationRows.length" title="当前条件没有欠交学生" description="可切换为“全部学生”查看完整应交台账。" />
        <DataTable
          v-else
          :columns="obligationColumns"
          :rows="obligationRows"
          row-key="recordId"
          :pagination="obligationPagination"
          @page-change="onObligationPage"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.studentName }}</div>
            <div class="mp-cell-sub">{{ row.studentNo }} · {{ row.advisorName || '未分配指导教师' }}</div>
          </template>
          <template v-for="kind in ['daily', 'weekly', 'monthly', 'summary']" :key="kind" #[`cell-${kind}`]="{ row }">
            <span>{{ obligationMetric(row[kind]) }}</span>
            <AppPermissionButton v-if="row[kind]?.missing > 0" code="internship.report.review" size="sm"
              :allowed="canRemind" reason="当前账号无催交权限，需要报告批阅权限"
              :disabled="!!reminding" @click="remindMissing(row, kind)">催交</AppPermissionButton>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :type="row.status === 'MISSING' ? 'warning' : (row.status === 'COMPLETE' ? 'success' : 'info')">
              {{ row.statusLabel }}
            </AppStatusTag>
            <div class="mp-cell-sub">{{ row.completionRate == null ? '完成率未配置' : ('完成率 ' + row.completionRate + '%') }}</div>
          </template>
        </DataTable>
      </section>

      <ModuleSummaryStrip v-if="!obligationOpen" :metrics="summaryMetrics" note="已交/缺交按本批次原单与配置累计计算；提交日期只筛选下方报告和导出台账。" />
      <!-- 报告类型切换（原「日报批阅 / 月报批阅 / 实习总结」独立菜单收口为页内切换） -->
      <div v-if="!obligationOpen" class="mp-tabs wr-tabs wr-tabs--type" aria-label="报告类型">
        <button v-for="t in typeTabs" :key="t.value" class="mp-tab" :class="{ 'is-active': reportTypeKey === t.value }" @click="switchType(t.value)">
          {{ t.label }}
        </button>
      </div>
      <div v-if="!obligationOpen" class="mp-tabs wr-tabs wr-tabs--status" aria-label="审核状态">
        <button v-for="t in activeTabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="!obligationOpen && error" :description="error" @retry="load" />
      <LoadingState v-else-if="!obligationOpen && loading" />
      <EmptyState v-else-if="!obligationOpen && !rows.length" :title="emptyTitle" description="可切换页签或调整筛选条件" />
      <DataTable
        v-else-if="!obligationOpen"
        :columns="activeColumns"
        :rows="rows"
        row-key="id"
        :selectable="filters.status === 'PENDING_REVIEW' && canBatchApprove"
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <label v-if="reportTypeKey === 'summary'">百分制评分<input v-model.trim="batchScore" type="number" min="0" max="100" step="0.01" :disabled="batchSubmitting" /></label>
          <label v-else>五级评价<select v-model="batchRating" :disabled="batchSubmitting"><option value="">请选择评价</option><option v-for="level in [1,2,3,4,5]" :key="level" :value="level">{{ level }}级</option></select></label>
          <AppPermissionButton
            code="internship.report.review"
            variant="secondary"
            size="sm"
            :allowed="canBatchApprove"
            :disabled="!selected.length || batchHasRisk || batchSubmitting"
            :loading="batchSubmitting"
            :reason="batchApproveReason"
            @click="batchApprove"
          >批量评分并通过</AppPermissionButton>
          <span class="mp-note" title="退回原因必填，需逐篇进入详情填写">批量退回不可用：退回原因必须逐篇填写</span>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ [row.className, row.enterpriseName].filter((item) => item && item !== '-' && item !== 'null').join(' · ') || '未关联班级或企业' }}</div>
        </template>
        <template #cell-version="{ row }">
          <AppStatusTag v-if="row.isResubmit" type="info">{{ versionLabel(row.reportVersion || row.version) }} 重交</AppStatusTag>
          <span v-else>{{ versionLabel(row.reportVersion || row.version) }}</span>
        </template>
        <template #cell-submitAt="{ row }">{{ formatDateTime(row.submitAt) }}</template>
        <template #cell-periodKey="{ row }">{{ row.periodLabel || (row.reportType === 'SUMMARY' ? '实习总结' : row.periodKey) }}</template>
        <template #cell-riskFlag="{ row }">
          <AppRiskTag v-if="row.riskFlag" :level="row.riskFlag" label="风险学生" />
          <span v-else class="mp-note">—</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-evaluation="{ row }">
          <span>{{ row.review?.summaryScore != null ? row.review.summaryScore + '分（百分制）' : row.review?.ratingLevel ? row.review.ratingLevel + '级（五级评价）' : '本次提交尚未评分' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <AppPermissionButton v-if="!isProcessReport && row.status === 'OVERDUE'" code="internship.report.review" variant="ghost" size="sm" :allowed="canRemind" reason="当前账号无催交权限，需要报告批阅权限" @click="remind(row)">催交</AppPermissionButton>
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
import ActionReceipt from './components/ActionReceipt.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { saveReviewQueue } from '@/modules/internship/composables/reviewQueue'
import { restoreWorkContext, captureWorkContext } from '@/modules/internship/composables/workContext'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { currentSessionGeneration } from '@/services/http/client'
import { formatDateTime } from '@/utils/dateUtils'

const WORK_FIELDS = ['pagination.page', 'filters.status', 'filters.keyword', 'filters.startDate', 'filters.endDate',
  'filterDraft.keyword', 'filterDraft.startDate', 'filterDraft.endDate']

const PANEL_STATUS = {
  all: '',
  review: 'PENDING_REVIEW',
  approved: 'APPROVED',
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
  { key: 'evaluation', title: '本次提交评价' },
  { key: 'actions', title: '操作', width: '80px' }
]

export default {
  name: 'WeeklyReportListView',
  components: { ModulePageShell, DataTable, AppStatusTag, AppRiskTag, AppExportButton,
    AppPermissionButton, LoadingState, ErrorState, EmptyState, ModuleSummaryStrip, ActionReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, loadSequence: 0, obligationSequence: 0,
      error: '',
      rows: [],
      selected: [],
      obligationOpen: false,
      obligationLoading: false,
      obligationError: '',
      obligationRows: [],
      obligationMissingOnly: true,
      obligationPagination: { page: 1, pageSize: 20, total: 0 },
      batchSubmitting: false, batchRating: '', batchScore: '', batchFailures: [], reminding: '',
      obligationSummary: null, statisticsError: '',
      lastReceipt: null,
      workContextReady: false,
      filters: { status: 'PENDING_REVIEW', keyword: '', startDate: '', endDate: '' },
      filterDraft: { keyword: '', startDate: '', endDate: '' },
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
      obligationColumns: [
        { key: 'student', title: '学生', width: '180px' },
        { key: 'daily', title: '日报', width: '180px' },
        { key: 'weekly', title: '周报', width: '180px' },
        { key: 'monthly', title: '月报', width: '180px' },
        { key: 'summary', title: '实习总结', width: '180px' },
        { key: 'status', title: '总体', width: '150px' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'week', title: '周次' },
        { key: 'submitAt', title: '提交时间' },
        { key: 'version', title: '版本' },
        { key: 'wordCount', title: '字数' },
        { key: 'attachments', title: '附件' },
        { key: 'riskFlag', title: '风险标记' },
        { key: 'status', title: '状态' },
        { key: 'evaluation', title: '本次提交评价' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    isProcessReport() {
      return !!TYPE_MAP[this.reportTypeKey]
    },
    typeConfig() {
      return TYPE_MAP[this.reportTypeKey] || null
    },
    pageTitle() {
      return this.isProcessReport ? `${this.typeConfig.label}批阅` : '周报批阅'
    },
    pageSubtitle() {
      if (this.isProcessReport) {
        return `核对${this.typeConfig.label}内容与材料，批阅结果同步学生。`
      }
      return '核对周报正文与重交修改，批阅结果同步学生。'
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
      const metrics = [{ label, value: this.pagination.total, tone: this.filters.status === 'PENDING_REVIEW' && this.pagination.total ? 'warn' : undefined }]
      const counts = this.obligationSummary?.[this.reportTypeKey || 'weekly']
      if (counts) metrics.push({ label: '本批次累计已交', value: counts.submitted },
        { label: '本批次应交', value: counts.configured ? counts.required : '未配置' },
        { label: '本批次缺交', value: counts.configured ? counts.missing : '未配置' })
      return metrics
    },
    exportLabel() {
      return this.isProcessReport ? `导出${this.typeConfig.label}` : '导出周报'
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
      return p ? !!p.allowed : canCode(this.ctx, 'internship.report.review')
    },
    canRemind() { return canCode(this.ctx, 'internship.report.review') },
    batchApproveReason() {
      if (this.batchHasRisk) return '所选含风险学生周报，需逐篇批阅'
      const p = this.perm.batchApproveReports
      if (p && !p.allowed) return p.reason || '无批量通过权限'
      if (!this.selected.length) return '请先勾选待批阅报告'
      return ''
    }
  },
  created() {
    // immediate watcher 会先按 URL 页签加载默认页码，但首次 load 不得覆盖已有工作上下文。
    const restored = restoreWorkContext(this, WORK_FIELDS, { skipWhenQuery: ['type', 'panel', 'page', 'keyword', 'startDate', 'endDate'] })
    this.workContextReady = true
    if (restored) this.load()
  },
  beforeUnmount() { this.loadSequence++; this.obligationSequence++ },
  watch: {
    'batchStore.selectedBatchId'() {
      this.pagination.page = 1
      this.obligationPagination.page = 1
      this.selected = []
      this.lastReceipt = null
      this.load()
      if (this.obligationOpen) this.loadObligations()
    },
    '$route.query': {
      immediate: true,
      handler(query) {
        this.reportTypeKey = String(query.type || '')
        this.lastReceipt = null
        this.batchFailures = []
        this.applyPanel(String(query.panel || (this.isProcessReport ? 'all' : 'review')))
        if (this.obligationOpen) this.loadObligations()
      }
    }
  },
  methods: {
    formatDateTime,
    versionLabel(value) { return `第${String(value || '').replace(/^v/, '') || '待核实'}版` },
    reportFilters() { return { ...this.filters, startDate: this.filters.startDate || undefined, endDate: this.filters.endDate || undefined } },
    applySearch() {
      if (this.filterDraft.startDate && this.filterDraft.endDate && this.filterDraft.startDate > this.filterDraft.endDate) {
        toast.error('开始日期不能晚于结束日期'); return
      }
      Object.assign(this.filters, this.filterDraft)
      this.pagination.page = 1; this.obligationPagination.page = 1
      const query = { ...this.$route.query, page: '1' }
      for (const key of ['keyword', 'startDate', 'endDate']) {
        if (this.filters[key]) query[key] = this.filters[key]
        else delete query[key]
      }
      const changed = ['keyword', 'startDate', 'endDate', 'page'].some(key => String(query[key] || '') !== String(this.$route.query[key] || ''))
      this.$router.replace({ path: this.$route.path, query })
      if (!changed) {
        if (this.obligationOpen) this.loadObligations()
        else this.load()
      }
    },
    toggleObligations() {
      this.obligationOpen = !this.obligationOpen
      if (this.obligationOpen) {
        this.obligationPagination.page = 1
        this.loadObligations()
      }
    },
    obligationMetric(metric) {
      if (!metric?.configured) return '未配置'
      return `应 ${metric.required} / 交 ${metric.submitted} / 通过 ${metric.approved} / 缺 ${metric.missing}`
    },
    setObligationMissing(value) {
      this.obligationMissingOnly = !!value
      this.obligationPagination.page = 1
      this.loadObligations()
    },
    onObligationPage(page) {
      this.obligationPagination.page = page
      this.loadObligations()
    },
    async loadObligations() {
      const batchId = this.batchStore.selectedBatchId, generation = currentSessionGeneration()
      const sequence = ++this.obligationSequence
      this.obligationRows = []; this.obligationPagination.total = 0
      if (!batchId) {
        this.obligationRows = []
        this.obligationPagination.total = 0
        this.obligationLoading = false; this.obligationError = '请先选择实习批次'
        return
      }
      this.obligationLoading = true
      this.obligationError = ''
      let res
      try { res = await internshipApi.getReportObligations({
        batchId,
        keyword: this.filters.keyword,
        missingOnly: this.obligationMissingOnly,
        page: this.obligationPagination.page,
        pageSize: this.obligationPagination.pageSize
      }) } catch {
        if (sequence === this.obligationSequence && batchId === this.batchStore.selectedBatchId && generation === currentSessionGeneration()) {
          this.obligationLoading = false; this.obligationError = '报告应交/未交台账读取失败，请重试'
        }
        return
      }
      if (sequence !== this.obligationSequence || batchId !== this.batchStore.selectedBatchId || generation !== currentSessionGeneration()) return
      this.obligationLoading = false
      if (res.code !== 0) {
        this.obligationError = res.message || '报告应交/未交台账加载失败'
        return
      }
      this.obligationRows = res.data?.items || []
      this.obligationPagination.total = Number(res.data?.total || 0)
      this.obligationPagination.page = Number(res.data?.page || 1)
      this.obligationPagination.pageSize = Number(res.data?.pageSize || 20)
    },
    exportObligationsFn() {
      return internshipApi.exportReportObligations({
        batchId: this.batchStore.selectedBatchId,
        keyword: this.filters.keyword,
        missingOnly: this.obligationMissingOnly
      })
    },
    goDetail(row) {
      const query = { ...this.$route.query, batchId: this.batchStore.selectedBatchId, page: String(this.pagination.page) }
      // 进入详情前保存连续批阅队列（仅当前页真实行，不伪造全量）
      const tab = this.activeTabs.find((t) => t.value === this.filters.status)
      const tabLabel = tab ? tab.label : '全部'
      saveReviewQueue({
        kind: this.isProcessReport ? 'process-report' : 'weekly-report',
        title: this.isProcessReport ? `${tabLabel} · ${this.typeConfig.label}` : tabLabel,
        listPath: this.$route.path,
        listQuery: query,
        ids: this.rows.map((r) => r.id)
      })
      if (this.isProcessReport) {
        this.$router.push({ path: `/admin/internship/process-reports/${row.id}`, query })
      } else {
        this.$router.push({ path: `/admin/internship/reports/${row.id}`, query })
      }
    },
    applyPanel(panel) {
      const status = Object.prototype.hasOwnProperty.call(PANEL_STATUS, panel) ? PANEL_STATUS[panel] : PANEL_STATUS.review
      this.filters.status = this.isProcessReport && status === 'OVERDUE' ? 'PENDING_REVIEW' : status
      for (const key of ['keyword', 'startDate', 'endDate']) {
        this.filters[key] = String(this.$route.query[key] || '')
        this.filterDraft[key] = this.filters[key]
      }
      this.pagination.page = Math.max(1, Number(this.$route.query.page) || 1)
      this.selected = []
      return this.load()
    },
    switchType(typeKey) {
      const query = { ...this.$route.query }
      if (typeKey) query.type = typeKey
      else delete query.type
      // 切换报告类型时状态页签回到「待批阅」
      query.panel = 'review'; query.page = '1'
      if (['type', 'panel', 'page'].every(key => String(query[key] || '') === String(this.$route.query[key] || ''))) this.applyPanel('review')
      else this.$router.replace({ path: this.$route.path, query })
    },
    switchTab(v) {
      const panel = Object.keys(PANEL_STATUS).find((k) => PANEL_STATUS[k] === v) || 'all'
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel, page: '1' } })
      } else {
        this.applyPanel(panel)
      }
    },
    onPageChange(page) {
      const query = { ...this.$route.query, page: String(page),
        panel: Object.keys(PANEL_STATUS).find(key => PANEL_STATUS[key] === this.filters.status) || 'all' }
      for (const key of ['keyword', 'startDate', 'endDate']) {
        if (this.filters[key]) query[key] = this.filters[key]
        else delete query[key]
      }
      if (String(this.$route.query.page) === String(page)) this.load()
      else this.$router.replace({ path: this.$route.path, query })
    },
    exportFn() {
      if (this.isProcessReport) {
        return internshipApi.exportProcessReports({
          ...this.reportFilters(),
          reportType: this.typeConfig.reportType,
          status: this.filters.status,
          batchId: this.batchStore.selectedBatchId
        })
      }
      return internshipApi.exportWeeklyReports({ ...this.reportFilters(), batchId: this.batchStore.selectedBatchId })
    },
    remind(row) {
      if (!this.canRemind || !row?.id) return
      internshipApi.remindWeeklyReport(row.id).then((res) => {
        if (res.code === 0) {
          const d = res.data || {}
          toast.success(d.reminded ? '催交已登记，请核对学生站内通知' : '未读到催交结果，请重新核对')
        } else {
          toast.error(res.message || '催交失败')
        }
      })
    },
    async remindMissing(row, kind) {
      if (!this.canRemind || this.reminding || !row[kind]?.missing) return
      const batchId = this.batchStore.selectedBatchId, sequence = this.obligationSequence
      this.reminding = `${row.recordId}:${kind}`
      try {
        const res = await internshipApi.remindReportObligation(row.recordId, { batchId, reportType: kind.toUpperCase() })
        if (batchId !== this.batchStore.selectedBatchId || sequence !== this.obligationSequence) return
        if (res.code === 0 && res.data?.queued) toast.success('催交已登记，站内通知等待发送')
        else toast.error(res.message || '催交未完成，请重试')
      } catch { toast.error('催交请求未完成，请重试') }
      finally { this.reminding = '' }
    },
    async batchApprove() {
      if (this.batchSubmitting || !this.canBatchApprove || this.batchHasRisk || !this.selected.length) return
      const summary = this.reportTypeKey === 'summary', score = Number(this.batchScore), rating = Number(this.batchRating)
      if (summary ? !String(this.batchScore ?? '').trim() || !Number.isFinite(score) || score < 0 || score > 100 : ![1,2,3,4,5].includes(rating)) {
        toast.error(summary ? '必须填写0到100分，0分有效' : '请先选择五级评价'); return
      }
      const items = this.rows.filter(row => this.selected.some(id => String(id) === String(row.id)))
      if (items.length !== this.selected.length || items.some(row => row.status !== 'PENDING_REVIEW' || row.version == null)) {
        toast.error('所选报告不是已读取的待批阅版本，请重新查询'); return
      }
      const batchId = this.batchStore.selectedBatchId, sequence = this.loadSequence, type = this.reportTypeKey,
        role = this.ctx.currentRole, scope = this.ctx.dataScope, generation = currentSessionGeneration()
      const current = () => batchId === this.batchStore.selectedBatchId && sequence === this.loadSequence && type === this.reportTypeKey &&
        role === this.ctx.currentRole && scope === this.ctx.dataScope && generation === currentSessionGeneration()
      this.batchSubmitting = true
      this.batchFailures = []
      let approved = 0, unconfirmed = false
      try {
        for (const row of items) {
          if (!current()) return
          const body = { action: 'APPROVE', comment: '批量评分通过', batchId, expectedVersion: row.version,
            ratingLevel: summary ? undefined : rating, summaryScore: summary ? score : undefined }
          try {
            // Existing authoritative command commits each document independently.
            const res = type ? await internshipApi.reviewProcessReport(row.id, body) : await internshipApi.reviewWeeklyReport(row.id, body)
            if (!current()) return
            // The API wrapper resolves transport failures instead of throwing them.
            if (typeof res?.code !== 'number' || [503001, 503002].includes(res.code)) throw new Error('审核结果待确认')
            if (res.code === 0) approved++
            else this.batchFailures.push({ id: row.id, studentName: row.studentName, message: res.message || '评分未完成，请打开原单核对' })
          } catch {
            if (!current()) return
            unconfirmed = true
            this.batchFailures.push({ id: row.id, studentName: row.studentName, message: '请求结果未确认，请刷新核对；未自动重试' })
            for (const pending of items.slice(items.indexOf(row) + 1)) this.batchFailures.push({ id: pending.id, studentName: pending.studentName, message: '尚未发送，待核对上一条结果后再办理' })
            break
          }
        }
        if (!current()) return
        this.lastReceipt = { statusLabel: unconfirmed ? '评分结果待核对' : (this.batchFailures.length ? '部分评分完成' : '批量评分完成'), actionLabel: '报告批量评分',
          objectLabel: unconfirmed ? `已确认完成 ${approved} 篇 · 另有 ${this.batchFailures.length} 篇需核对或待处理` : `完成 ${approved} 篇 · 未完成 ${this.batchFailures.length} 篇`, auditText: '成功记录分别提交评分、状态和审计，失败记录不自动重做',
          nextStep: unconfirmed ? '先刷新核对结果未确认的原单，再继续尚未发送的报告' : (this.batchFailures.length ? '按下方逐篇回执核对原单后继续' : '学生可刷新查看本次提交的评价') }
        this.selected = []
        await this.load()
      } finally {
        this.batchSubmitting = false
      }
    },
    async load() {
      const sequence = ++this.loadSequence, batchId = this.batchStore.selectedBatchId, generation = currentSessionGeneration()
      const current = () => sequence === this.loadSequence && batchId === this.batchStore.selectedBatchId && generation === currentSessionGeneration()
      this.rows = []; this.selected = []; this.pagination.total = 0; this.obligationSummary = null; this.statisticsError = ''
      if (this.workContextReady) captureWorkContext(this, WORK_FIELDS)
      this.loading = true
      this.error = ''
      const params = { ...this.reportFilters(), page: this.pagination.page, pageSize: this.pagination.pageSize, batchId: this.batchStore.selectedBatchId }
      let res
      try { res = this.isProcessReport
        ? await internshipApi.getProcessReports({ ...params, reportType: this.typeConfig.reportType })
        : await internshipApi.getWeeklyReports(params)
      } catch {
        if (current()) { this.loading = false; this.error = '报告读取失败，请重试查询' }
        return
      }
      if (!current()) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
      if (res.code === 0) {
        try {
          const stats = await internshipApi.getReportObligations({ batchId, keyword: this.filters.keyword, page: 1, pageSize: 1 })
          if (!current()) return
          if (stats.code === 0 && stats.data?.summary) this.obligationSummary = stats.data.summary
          else this.statisticsError = '报告已读取，应交与缺交统计暂未读取，请重试查询'
        } catch { if (current()) this.statisticsError = '应交与缺交统计读取失败，请重试查询' }
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.wr-search { display:flex; flex-wrap:wrap; gap:12px; align-items:end; }
.wr-search label { display:grid; gap:6px; font-size:12px; }
.wr-search input, .wr-search button { min-height:36px; padding:6px 10px; border:1px solid var(--card-b); border-radius:6px; background:var(--card); color:var(--t1); box-sizing:border-box; }
.wr-batch-failures { padding:12px; border:1px solid #efc77a; border-radius:8px; font-size:13px; }
.wr-obligation { display:grid; gap:12px; padding:16px; border:1px solid var(--card-b); border-radius:12px; background:var(--card); }
.wr-obligation__head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.wr-obligation__head strong { font-size:16px; color:var(--t1); }
.wr-obligation__head p { margin:5px 0 0; font-size:12px; color:var(--t3); line-height:1.6; }
.wr-obligation__filters { display:flex; gap:6px; flex-wrap:wrap; }
.wr-obligation__filters .mp-tab { padding:7px 12px; border:1px solid var(--card-b); border-radius:8px; background:var(--card); color:var(--t2); cursor:pointer; }
.wr-obligation__filters .mp-tab.is-active { border-color:var(--pri-100); background:var(--pri-bg); color:var(--pri); font-weight:600; }
.wr-tabs { display: flex; gap: 6px; padding: 7px; border: 1px solid var(--card-b); border-radius: 12px; background: var(--card); box-shadow: var(--s1); overflow-x: auto; }
.wr-tabs--type { background: linear-gradient(100deg, var(--pri-bg), var(--card) 52%); }
.wr-tabs--status { margin-top: -8px; padding-left: 14px; border-top: 0; border-radius: 0 0 12px 12px; box-shadow: none; }
.wr-tabs .mp-tab { position: relative; flex: 0 0 auto; padding: 7px 12px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2); font-size: 12px; transition: .16s ease; }
.wr-tabs .mp-tab:hover { color: var(--pri); background: var(--pri-bg); }
.wr-tabs .mp-tab.is-active { border-color: var(--pri-100); background: var(--card); color: var(--pri); font-weight: var(--font-weight-semibold); box-shadow: 0 2px 5px rgba(15, 40, 90, .07); }
.wr-tabs--status .mp-tab.is-active { background: var(--pri-bg); box-shadow: none; }
</style>
