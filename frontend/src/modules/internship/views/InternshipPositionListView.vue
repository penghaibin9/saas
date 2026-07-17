<template>
  <ModulePageShell
    title="企业与岗位"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton v-if="activePanel !== 'stats'" :export-fn="exportFn">⬇ 导出 Excel 台账</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div v-if="activePanel === 'stats' && posStats" class="mp-stats">
      <AppMetricCard title="岗位总数" :value="posStats.total" />
      <AppMetricCard title="风险岗位" :value="posStats.riskCount" :accent="posStats.riskCount ? 'risk' : 'primary'" />
      <AppMetricCard title="已上架容量" :value="posStats.publishedCapacity" />
      <AppMetricCard title="已分配" :value="posStats.publishedAllocated" />
      <AppMetricCard title="容量利用率" :value="posStats.capacityUtilization" unit="%" />
      <AppMetricCard title="不限专业(上架)" :value="posStats.unlimitedMajorCount" />
    </div>

    <div class="mp-stack">
      <AdvancedFilter v-if="activePanel !== 'stats'" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="activePanel === 'stats' && posStats">
        <div class="ip-block">
          <h3 class="ip-h">按状态</h3>
          <DataTable :columns="statStatusCols" :rows="posStats.byStatus || []" row-key="status" :pagination="null" />
        </div>
        <div class="ip-block">
          <h3 class="ip-h">按专业要求（已上架）</h3>
          <EmptyState v-if="!(posStats.byMajor || []).length" title="暂无已上架岗位" description="上架岗位后可按专业要求聚合统计" />
          <DataTable v-else :columns="statMajorCols" :rows="posStats.byMajor || []" row-key="major" :pagination="null" />
        </div>
      </template>
      <EmptyState v-else-if="!rows.length" title="暂无岗位" description="可「＋ 新增岗位」或「导入」补充岗位库（岗位须先有企业）" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-position="{ row }">
          <div class="mp-cell-main">{{ row.title }}<span v-if="row.riskFlag" class="ip-risk">⚠风险</span></div>
          <div class="mp-cell-sub">{{ row.companyName }}</div>
        </template>
        <template #cell-require="{ row }">
          <div class="mp-cell-sub">{{ row.majorRequirement || '不限专业' }}</div>
          <div class="mp-cell-sub">{{ row.gradeRequirement || '不限年级' }}</div>
        </template>
        <template #cell-capacity="{ row }">{{ row.allocatedCount }}/{{ row.headcount }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/positions/' + row.id)">详情</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link" style="margin-left: var(--space-2)" @click="$router.push('/admin/internship/positions/' + row.id + '/edit')">编辑</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'SUBMIT')">提交</button>
          <button v-else-if="['PENDING', 'OFFLINE', 'SUSPENDED'].includes(row.status)" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'PUBLISH')">上架</button>
          <button v-else-if="row.status === 'PUBLISHED'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'OFFLINE')">下架</button>
          <button v-if="row.status !== 'ARCHIVED' && row.status !== 'RISK'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askRisk(row, true)">标记风险</button>
          <button v-if="row.status === 'RISK'" class="mp-link" style="margin-left: var(--space-2)" @click="askRisk(row, false)">解除风险</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑：独立表单页 /admin/internship/positions/new 与 /:id/edit（PositionFormView） -->

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入岗位"
      template-name="岗位导入模板.xlsx"
      :required-fields="['岗位名称', '关联企业']"
      :preview-fields="['title', 'company', 'major', 'location', 'headcount']"
      :download-template-fn="() => positionApi.downloadPositionTemplate()"
      :upload-fn="(file) => positionApi.importPositionsXlsx(file)"
      :confirm-fn="({ rows }) => positionApi.importPositionsConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => positionApi.downloadPositionImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 岗位库列表（/admin/internship/positions）：筛选 + 状态机 + 风险标记 + 真导入导出；新增/编辑走独立表单页 PositionFormView。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag, AppMetricCard } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { positionApi } from '@/modules/internship/api/position.api'
import { POSITION_STATUS } from '@/modules/internship/constants/position.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', companyId: '', risk: '' })
const POSITION_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  detail: () => EMPTY_FILTERS(),
  requirement: () => EMPTY_FILTERS(),
  capacity: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  publish: () => ({ ...EMPTY_FILTERS(), status: 'PENDING' }),
  offline: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  risk: () => ({ ...EMPTY_FILTERS(), risk: 'true' }),
  archive: () => ({ ...EMPTY_FILTERS(), status: 'ARCHIVED' }),
  stats: () => EMPTY_FILTERS()
}
const POSITION_PANEL_HINTS = {
  list: '岗位关联企业 · 黑名单/停用企业不可上架',
  detail: '点击行「详情」进入岗位详情页',
  requirement: '关注「专业/年级」列 · 新建/编辑可维护要求',
  capacity: '已上架岗位 · 关注「已分配/容量」列',
  publish: '待审核岗位 · 行内可「上架」',
  offline: '已上架岗位 · 行内可「下架」',
  risk: '仅风险岗位 · 可「解除风险」',
  archive: '已归档岗位台账',
  stats: '岗位库真实统计 · 状态分布 / 专业分布 / 容量利用率'
}

export default {
  name: 'InternshipPositionListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppMetricCard, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      positionApi,
      loading: true, error: '', submitting: false, activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      enterpriseOpts: [], posStats: null,
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'position', title: '岗位 / 企业' },
        { key: 'require', title: '专业 / 年级' },
        { key: 'workLocation', title: '工作地点' },
        { key: 'salaryRange', title: '薪资' },
        { key: 'capacity', title: '已分配/容量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '270px' }
      ],
      statStatusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      statMajorCols: [
        { key: 'major', title: '专业要求' },
        { key: 'count', title: '岗位数' },
        { key: 'capacity', title: '容量' },
        { key: 'allocated', title: '已分配' }
      ]
    }
  },
  computed: {
    statusOpts() { return POSITION_STATUS },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '岗位 / 企业 / 专业' },
        { key: 'status', label: '状态', type: 'select', options: this.statusOpts },
        { key: 'companyId', label: '企业', type: 'select', options: this.enterpriseOpts.map((e) => ({ value: e.id, label: e.name })) },
        { key: 'risk', label: '风险', type: 'select', options: [{ value: 'true', label: '仅风险岗位' }] }
      ]
    },
    toolbarActions() {
      if (this.activePanel === 'stats') {
        return [{ key: 'refreshStats', label: '刷新统计', variant: 'primary' }]
      }
      return [{ key: 'create', label: '＋ 新增岗位', variant: 'primary' }, { key: 'import', label: '导入' }]
    },
    pageSubtitle() {
      const hint = POSITION_PANEL_HINTS[this.activePanel] || POSITION_PANEL_HINTS.list
      if (this.activePanel === 'stats' && this.posStats) {
        return `${hint} · 共 ${this.posStats.total} 个岗位`
      }
      return `共 ${this.total} 个岗位 · ${hint}`
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  async created() {
    const e = await positionApi.getEnterpriseOptions()
    if (e.code === 0) this.enterpriseOpts = e.data
  },
  methods: {
    applyPanel(panel) {
      const key = POSITION_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (POSITION_PANEL_PRESETS[key] || POSITION_PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      if (this.activePanel === 'stats') {
        const res = await positionApi.getPositionStats()
        if (res.code === 0) { this.posStats = res.data; this.rows = []; this.total = 0 }
        else this.error = res.message
        this.loading = false
        return
      }
      this.posStats = null
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      if (p.risk === '') delete p.risk
      const res = await positionApi.getPositions(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { this.$router.push('/admin/internship/positions/new') }
      if (key === 'import') { this.importVisible = true }
      if (key === 'refreshStats') this.load()
    },
    exportFn() {
      return positionApi.exportPositions({ ...this.filters })
    },
    onImported(data) {
      toast.success(`已导入 ${data.created || 0} 个岗位（草稿）`)
      this.load()
    },
    askStatus(row, action) {
      const map = { SUBMIT: { t: '提交审核', c: '确认提交', type: 'primary' }, PUBLISH: { t: '上架岗位', c: '确认上架', type: 'primary' }, OFFLINE: { t: '下架岗位', c: '确认下架', type: 'warning' } }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.title}」执行「${m.t}」？${action === 'PUBLISH' ? '（黑名单/非合作中企业将被拒）' : ''}`, type: m.type, confirmText: m.c, requireReason: false, action: 'STATUS_' + action, row }
    },
    askRisk(row, on) {
      this.confirm = { visible: true, title: on ? '标记风险岗位' : '解除风险', message: on ? `确认将「${row.title}」标记为风险岗位？` : `确认解除「${row.title}」的风险标记？（回到已下架）`, type: on ? 'danger' : 'primary', confirmText: on ? '确认标记' : '确认解除', requireReason: on, reasonLabel: '风险说明', action: on ? 'RISK_ON' : 'RISK_OFF', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await positionApi.setPositionStatus(row.id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'RISK_ON') res = await positionApi.markPositionRisk(row.id, { on: true, note: reason || '' })
        else if (action === 'RISK_OFF') res = await positionApi.markPositionRisk(row.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ip-risk { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.mp-stats { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stats > * { flex: 1 1 160px; }
.ip-block { margin-bottom: var(--space-4); }
.ip-h { margin: 0 0 var(--space-2); font-size: 14px; }
</style>
