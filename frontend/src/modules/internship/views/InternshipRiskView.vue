<template>
  <ModulePageShell
    title="风险预警"
    subtitle="按风险等级和处理期限排查问题，进入处置详情继续跟进。"
    :role-name="ctx.currentRole?.roleName || '教师 / 管理员'"
    :data-scope-name="ctx.dataScope?.scopeName || '当前授权范围'" :watermark="false"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" :has-permission="canExport" @exported="onExported">导出风险台账</AppExportButton>
    </template>

    <ModuleSummaryStrip v-if="summaryMetrics.length" :metrics="summaryMetrics" />

    <div class="mp-stack">
      <nav class="ir-focus" aria-label="风险处置视图">

        <button
          v-for="focus in focusViews"
          :key="focus.key"
          type="button"
          class="ir-focus__item"
          :class="{ 'is-active': activePanel === focus.key }"
          @click="goPanel(focus.key)"
        >{{ focus.label }}</button>
      </nav>
      <AppSearchBox v-model="filters.keyword" placeholder="搜索学生姓名或学号" @search="search" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前筛选下暂无风险记录" description="可调整风险类型、等级或跟进状态。"><template #actions><AppButton variant="ghost" @click="reset">清空筛选</AppButton></template></EmptyState>
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-source="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ sourceText(row.source) }}</div>
          <div class="mp-cell-sub">{{ row.sourceDetail }}</div>
        </template>
        <template #cell-level="{ row }">
          <AppRiskTag :level="row.level" />
        </template>
        <template #cell-deadline="{ row }">
          <span :style="isUrgent(row.deadline) ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.deadline }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button type="button" class="mp-link" @click="goStudent(row)">学生档案</button>
          <button
            v-if="canHandle && row.status !== 'CLOSED' && row.status !== 'RESOLVED'" type="button"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="goDispose(row)"
          >去处置</button>
          <button v-if="canHandle && !['CLOSED', 'RESOLVED'].includes(row.status)" type="button" class="mp-link" :disabled="remindingIds.includes(String(row.id))" style="margin-left: var(--space-2)" @click="remind(row)">{{ remindingIds.includes(String(row.id)) ? '催办中…' : '催办' }}</button>
        </template>
      </DataTable>


    </div>
  </ModulePageShell>
</template>

<script>
/** 风险学生列表（/admin/internship/risks）：风险等级 / 跟进状态 / 责任人 / 处理期限。 */
import {
  ModulePageShell, AdvancedFilter, DataTable,
  LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppStatusTag, AppRiskTag, AppExportButton, AppSearchBox } from '@/components/common'
import { AppButton } from '@/components/ui'
import { canCode } from '@/modules/internship/composables/permission'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { riskApi } from '@/modules/internship/api/leave-risk.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'
import { safeLocalizedText } from '@/utils/presentationSafety'

const EMPTY_FILTERS = () => ({ level: '', status: '', riskCode: '', keyword: '' })
const PANEL_PRESETS = {
  board: () => EMPTY_FILTERS(),
  'no-position': () => ({ level: '', status: '', riskCode: 'INT-R02' }),
  'no-checkin': () => ({ level: '', status: '', riskCode: 'INT-R07' }),
  'report-overdue': () => ({ level: '', status: '', riskCode: 'INT-R10' }),
  'leave-post': () => ({ level: '', status: 'PENDING_HANDLE', riskCode: 'INT-R06' }),
  // leave-post=请假未返岗待处理；leave-overdue=超期未归跟进中（同 INT-R06，按状态分桶）
  'leave-overdue': () => ({ level: '', status: 'PROCESSING', riskCode: 'INT-R06' }),
  'off-post': () => ({ level: 'HIGH', status: '', riskCode: 'INT-GUIDE' })
}

export default {
  name: 'InternshipRiskView',
  components: { ModulePageShell, AppSearchBox, AppButton, AdvancedFilter, DataTable, AppStatusTag, AppRiskTag, AppExportButton,
    LoadingState, ErrorState, EmptyState, ModuleSummaryStrip },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '', listSequence: 0, remindingIds: [],
      rows: [],
      filters: EMPTY_FILTERS(), activePanel: 'board',
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'source', title: '风险来源' },
        { key: 'level', title: '等级' },
        { key: 'owner', title: '责任人' },
        { key: 'deadline', title: '处理期限' },
        { key: 'lastFollow', title: '最近跟进' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    }
  },
  computed: {
    canHandle() { return canCode(this.ctx, 'internship.risk.handle') },
    focusViews() {
      return [
        { key: 'board', label: '全部风险' },
        { key: 'no-position', label: '未落岗' },
        { key: 'no-checkin', label: '打卡异常' },
        { key: 'report-overdue', label: '报告逾期' },
        { key: 'leave-post', label: '请假未返岗' },
        { key: 'leave-overdue', label: '超期未归' },
        { key: 'off-post', label: '离岗异常' }
      ]
    },
    filterFields() {
      return [
        { key: 'level', label: '风险等级', type: 'select', options: (this.ctx.statusOptions?.riskLevel || []) },
        {
          key: 'status', label: '跟进状态', type: 'select',
          options: [
            { value: 'PENDING_HANDLE', label: '待处理' },
            { value: 'PROCESSING', label: '跟进中' }
          ]
        }
      ]
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      return [{ label: '当前筛选风险记录', value: this.pagination.total, tone: this.pagination.total ? 'warn' : undefined }]
    },
    canExport() {
      const pa = this.ctx.permissionActions?.exportRiskList
      if (pa && typeof pa.allowed === 'boolean') return pa.allowed
      return false
    },
    batchStore() { return useInternshipBatchStore() }
  },
  watch: {
    '$route.query': {
      immediate: true,
      deep: true,
      handler() { this.applyPanel(String(this.$route.query.panel || 'board')) }
    },
    'batchStore.selectedBatchId'() {
      this.pagination.page = 1
      this.remindingIds = []
      this.syncQuery()
    }
  },
  methods: {
    sourceText(value) { return safeLocalizedText({ value, unknownLabel: '其他风险来源' }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return riskApi.exportRisks({ ...this.filters, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.board
      this.activePanel = PANEL_PRESETS[panel] ? panel : 'board'
      const query = this.$route.query
      this.filters = { ...EMPTY_FILTERS(), ...preset() }
      for (const key of Object.keys(this.filters)) { if (query[key] != null) this.filters[key] = String(query[key]) }
      this.pagination.page = Math.max(1, Number.parseInt(query.page, 10) || 1)
      this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({
        path: this.$route.path,
        query: this.batchStore.withBatchQuery({ panel, page: '1' })
      })
    },
    goStudent(row) {
      this.$router.push({
        path: '/admin/internship/students/' + row.internId,
        query: this.batchStore.withBatchQuery({})
      })
    },
    goDispose(row) {
      this.$router.push({
        path: '/admin/internship/risk-disposal',
        query: this.batchStore.withBatchQuery({ id: row.id })
      })
    },
    isUrgent(d) {
      const day = (d || '').toString().slice(0, 10)
      if (!day) return false
      const due = new Date(day.replace(/-/g, '/'))
      if (Number.isNaN(due.getTime())) return false
      const diff = (due.getTime() - Date.now()) / (24 * 3600 * 1000)
      return diff <= 3
    },
    syncQuery() {
      const query = this.batchStore.withBatchQuery({ panel: this.activePanel, page: String(this.pagination.page), ...this.filters })
      const current = this.$route.query || {}
      const keys = new Set([...Object.keys(query), ...Object.keys(current)])
      if ([...keys].every(key => String(query[key] || '') === String(current[key] || ''))) this.load()
      else this.$router.replace({ query })
    },
    onPageChange(page) { this.pagination.page = page; this.syncQuery() },
    search() { this.pagination.page = 1; this.syncQuery() },
    reset() {
      this.activePanel = 'board'; this.filters = EMPTY_FILTERS()
      this.pagination.page = 1; this.syncQuery()
    },
    async remind(row) {
      const id = String(row.id)
      if (!this.canHandle || ['CLOSED', 'RESOLVED'].includes(row.status) || this.remindingIds.includes(id)) return
      const batchId = this.batchStore.selectedBatchId
      this.remindingIds = [...this.remindingIds, id]
      const res = await riskApi.remind(id)
      if (batchId !== this.batchStore.selectedBatchId) return
      this.remindingIds = this.remindingIds.filter(value => value !== id)
      if (res.code !== 0) { toast.error(res.message || '催办失败'); return }
      const owner = res.data?.ownerName || row.owner || '责任人'
      toast.success(`已提醒 ${owner} 跟进该风险`)
    },
    async load() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.pagination.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.rows = []
        this.pagination.total = 0
        this.error = '请先选择实习批次'
        return
      }
      this.loading = true
      this.error = ''
      const res = await internshipApi.getRiskStudents({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize,
        batchId: this.batchStore.selectedBatchId
      })
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message || '风险记录加载失败'
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ir-focus { display: flex; align-items: center; gap: 6px; padding: 4px 0 12px; border-bottom: 1px solid var(--border-light); overflow-x: auto; }
.ir-focus__item { flex: 0 0 auto; padding: 6px 11px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2); cursor: pointer; font-size: 12px; transition: .16s ease; }
.ir-focus__item:hover { color: var(--primary-600); background: var(--primary-50); }
.ir-focus__item.is-active { border-color: var(--primary-100); background: var(--card); color: var(--primary-600); box-shadow: 0 2px 5px rgba(127, 29, 29, .08); font-weight: var(--font-weight-semibold); }
</style>
