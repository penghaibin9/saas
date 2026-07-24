<template>
  <ModulePageShell
    title="实习批次设置"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习批次管理"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn">⬇ 导出 Excel 台账</AppExportButton>
    </template>
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleSummaryStrip :metrics="summaryMetrics" />
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 个批次 · 状态流转全程留痕`" @action="onToolbar" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无实习批次" description="点击右上角「新建批次」创建本轮岗位实习" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        row-clickable
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
        @row-click="openDetail"
      >
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTagType[row.status] || 'default'" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-term="{ row }">
          <span>{{ row.academicYear || '—' }}{{ row.term ? ' · ' + row.term : '' }}</span>
        </template>
        <template #cell-range="{ row }">
          <span>{{ dateShort(row.startDate) || '—' }} ~ {{ dateShort(row.endDate) || '—' }}</span>
        </template>
        <template #cell-count="{ row }">
          <span>{{ row.actualCount }} / {{ row.plannedCount }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新建/编辑/详情已升级为独立页：/batches/new、/batches/:id/edit、/batches/:id -->

      <!-- 启用 / 结束 / 归档 / 作废 二次确认 -->
      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        :require-reason="confirmConf.requireReason"
        reason-label="作废原因（≥5 字）"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * /admin/internship/batches 实习批次列表（筛选 / 台账导出 / 启用 / 结束 / 归档 / 作废；真实走后端 /internship/batches）。
 * 新建/编辑入口跳独立页 BatchFormView（/batches/new、/batches/:id/edit）；详情跳 BatchDetailView（/batches/:id）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog, AppStatusTag, AppExportButton } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/internship/components'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { formatDate } from '@/utils/dateUtils'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })
const BATCH_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  timeline: () => ({ ...EMPTY_FILTERS(), status: 'RUNNING' }),
  rules: () => ({ ...EMPTY_FILTERS(), status: 'DRAFT' }),
  export: () => ({ ...EMPTY_FILTERS(), status: 'ARCHIVED' })
}
const BATCH_PANEL_HINTS = {
  list: '组织岗位实习的时间轴与规则骨架（草稿 → 进行中 → 已结束 → 已归档）',
  timeline: '进行中批次 · 点击行「详情」查看阶段时间轴，新建/编辑可配 stagesJson',
  rules: '草稿批次 · 新建/编辑时可编辑 rulesJson（打卡/周报/指导/评价/成绩）',
  export: '已归档批次台账 · 可用右上角「导出 Excel 台账」'
}
const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'RUNNING', label: '进行中' },
  { value: 'CLOSED', label: '已结束' },
  { value: 'ARCHIVED', label: '已归档' },
  { value: 'VOIDED', label: '已作废' }
]

export default {
  name: 'InternshipBatchListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState,
    AppConfirmDialog, AppStatusTag, AppExportButton, TableActionColumn, NoPermissionState,
    ModuleSummaryStrip
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      activePanel: 'list',
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      confirmVisible: false,
      confirmMode: '',
      confirmRow: null,
      statusTagType: { DRAFT: 'default', RUNNING: 'success', CLOSED: 'info', ARCHIVED: 'default', VOIDED: 'danger' }
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    noPermission() {
      // 批次列表查看本身对已授权进入本页的角色开放；创建/归档等动作按钮各自受权限控制（见 rowActions/toolbarActions）
      return false
    },
    toolbarActions() {
      const p = this.perms.createBatch
      return [
        { key: 'create', label: '新建批次', disabled: p ? !p.allowed : false, disabledReason: p && !p.allowed ? p.reason : '' }
      ]
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '批次名称 / 编号' },
        { key: 'status', label: '状态', type: 'select', options: STATUS_OPTIONS }
      ]
    },
    tableColumns() {
      return [
        { key: 'batchName', title: '批次名称' },
        { key: 'batchNo', title: '批次编号' },
        { key: 'term', title: '学年学期' },
        { key: 'range', title: '实习起止' },
        { key: 'count', title: '实际/计划人数' },
        { key: 'status', title: '状态' },
        { key: 'updateTime', title: '更新时间' },
        { key: 'actions', title: '操作' }
      ]
    },
    confirmConf() {
      const r = this.confirmRow
      if (this.confirmMode === 'activate') {
        return { title: '启用批次', message: r ? `将「${r.batchName}」置为「进行中」，实习流程正式开放。` : '', type: 'primary', confirmText: '确认启用', requireReason: false }
      }
      if (this.confirmMode === 'close') {
        return { title: '结束批次', message: r ? `将「${r.batchName}」置为「已结束」，结束后才可归档。` : '', type: 'danger', confirmText: '确认结束', requireReason: false }
      }
      if (this.confirmMode === 'archive') {
        return { title: '归档批次', message: r ? `归档「${r.batchName}」后进入只读台账，不可再变更。` : '', type: 'danger', confirmText: '确认归档', requireReason: false }
      }
      if (this.confirmMode === 'void') {
        return { title: '作废批次', message: r ? `作废「${r.batchName}」（仅草稿态可作废，可审计）。` : '', type: 'danger', confirmText: '确认作废', requireReason: true }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    },
    pageSubtitle() {
      const hint = BATCH_PANEL_HINTS[this.activePanel] || BATCH_PANEL_HINTS.list
      return `创建和管理实习批次，并设置打卡、周报、指导、评价和成绩规则 · ${hint}`
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const m = [{ label: '批次总数', value: this.total }]
      const running = this.rows.filter((r) => r.status === 'RUNNING').length
      if (running) m.push({ label: '本页进行中', value: running, tone: 'good' })
      return m
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
    const ctx = await internshipApi.getContext()
    if (ctx.code === 0) this.ctx = ctx.data
  },
  methods: {
    applyPanel(panel) {
      const key = BATCH_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (BATCH_PANEL_PRESETS[key] || BATCH_PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await internshipApi.getBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    dateShort(v) {
      return formatDate(v, '')
    },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    exportFn() {
      return internshipApi.exportBatches({ ...this.filters })
    },
    openCreate() {
      this.$router.push('/admin/internship/batches/new')
    },
    openEdit(row) {
      this.$router.push(`/admin/internship/batches/${row.id}/edit`)
    },
    openDetail(row) {
      this.$router.push(`/admin/internship/batches/${row.id}`)
    },
    rowActions(row) {
      return [
        { key: 'detail', label: '详情' },
        { key: 'edit', label: '编辑', disabled: row.status !== 'DRAFT', disabledReason: '仅草稿批次可编辑' },
        { key: 'activate', label: '启用', disabled: row.status !== 'DRAFT', disabledReason: '仅草稿可启用' },
        { key: 'close', label: '结束', disabled: row.status !== 'RUNNING', disabledReason: '仅进行中可结束' },
        { key: 'archive', label: '归档', disabled: row.status !== 'CLOSED', disabledReason: '仅已结束可归档' },
        { key: 'void', label: '作废', danger: true, disabled: row.status !== 'DRAFT', disabledReason: '仅草稿可作废' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.openDetail(row)
      if (key === 'edit') return this.openEdit(row)
      this.confirmMode = key
      this.confirmRow = row
      this.confirmVisible = true
    },
    async onConfirm(payload) {
      const row = this.confirmRow
      if (!row) return
      const reason = (payload && payload.reason) || ''
      let res
      if (this.confirmMode === 'activate') res = await internshipApi.activateBatch(row.id, { expectedVersion: row.version })
      else if (this.confirmMode === 'close') res = await internshipApi.closeBatch(row.id, { expectedVersion: row.version })
      else if (this.confirmMode === 'archive') res = await internshipApi.archiveBatch(row.id, { expectedVersion: row.version })
      else if (this.confirmMode === 'void') res = await internshipApi.voidBatch(row.id, reason)
      if (res && res.code === 0) {
        toast.success('操作成功')
        this.confirmVisible = false
        await this.load()
      } else {
        toast.error((res && res.message) || '操作失败')
      }
    }
  }
}
</script>
