<template>
  <ModulePageShell title="就业材料审核" subtitle="就业协议 / 劳动合同 / 升学入伍证明等材料核验" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业材料审核">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 份材料 · 审核动作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无待处理材料" description="当前筛选条件下没有就业材料" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        row-clickable
        @row-click="viewDetail"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-materialType="{ row }">{{ labelOf('materialType', row.materialType) }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="materialTagType[row.status] || 'default'" :label="labelOf('materialStatus', row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 单份退回 -->
      <AppConfirmDialog
        v-model:visible="returnVisible"
        title="退回材料"
        :message="returnTarget ? `退回「${returnTarget.name}」提交的《${returnTarget.fileName}》，学生将收到补充通知。` : ''"
        type="warning"
        confirm-text="确认退回"
        require-reason
        reason-label="退回原因"
        reason-placeholder="请写明缺失或不合规内容，便于学生补充（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onReturnConfirm"
      />

      <!-- 批量退回 -->
      <AppConfirmDialog
        v-model:visible="batchReturnVisible"
        title="批量退回材料"
        :message="`将退回选中的 ${selected.length} 份材料，退回原因将统一发送给相关学生。`"
        type="warning"
        confirm-text="确认批量退回"
        require-reason
        reason-label="退回原因"
        :submitting="submitting"
        @confirm="onBatchReturnConfirm"
      />

      <!-- 批量通过 -->
      <AppConfirmDialog
        v-model:visible="batchApproveVisible"
        title="批量通过材料"
        :message="`确认通过选中的 ${selected.length} 份材料？通过后学生就业记录标记为已核验。`"
        type="primary"
        confirm-text="确认批量通过"
        :submitting="submitting"
        @confirm="onBatchApproveConfirm"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出审核记录"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="审核留痕 · 就业材料">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 4：/admin/employment/materials 就业材料审核列表（通过 / 退回必填原因 / 批量 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { TableActionColumn, BatchActionBar, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { MATERIAL_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', materialType: '' })

export default {
  name: 'EmploymentMaterialListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppDrawer,
    TableActionColumn,
    BatchActionBar,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      selected: [],
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      returnVisible: false,
      returnTarget: null,
      batchReturnVisible: false,
      batchApproveVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      materialTagType: MATERIAL_TAG_TYPE
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
      const p = this.perms['employment.record.view']
      return p ? !p.allowed : false
    },
    canReview() {
      const p = this.perms['employment.material.review']
      return p ? p.allowed : true
    },
    reviewReason() {
      return this.perms['employment.material.review']?.reason || ''
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名 / 文件名' },
        { key: 'status', label: '审核状态', type: 'select', options: this.statusOptions.materialStatus || [] },
        { key: 'materialType', label: '材料类型', type: 'select', options: this.statusOptions.materialType || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['employment.material.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出审核记录', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '审核留痕' }
      ].filter(Boolean)
    },
    batchBarActions() {
      return this.batchDefs
        .map((b) => {
          const p = this.perms[b.permission]
          if (p && !p.visible) return null
          return { ...b, disabled: p ? !p.allowed : false, disabledReason: p?.reason }
        })
        .filter(Boolean)
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    async init() {
      const [ctx, status, cols, batch, exp] = await Promise.all([
        api.getEmploymentContext(),
        api.getStatusOptions(),
        api.getFieldColumns('materialList'),
        api.getBatchActions('materialList'),
        api.getExportOptions('materialList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (exp.code === 0) this.exportOpts = exp.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getEmploymentMaterials({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
    viewDetail(row) {
      this.$router.push(`/admin/employment/materials/${row.id}`)
    },
    rowActions(row) {
      const pending = ['SUBMITTED', 'REVIEWING'].includes(row.status)
      return [
        { key: 'view', label: '查看材料' },
        { key: 'approve', label: '通过', disabled: !this.canReview || !pending, disabledReason: !pending ? '仅待审核/审核中材料可操作' : this.reviewReason },
        { key: 'return', label: '退回', danger: true, disabled: !this.canReview || !pending, disabledReason: !pending ? '仅待审核/审核中材料可操作' : this.reviewReason }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') this.viewDetail(row)
      if (key === 'approve') this.doApprove(row)
      if (key === 'return') {
        this.returnTarget = row
        this.returnVisible = true
      }
    },
    async doApprove(row) {
      const res = await api.approveMaterial(row.id, {})
      if (res.code === 0) {
        toast.success(`已通过《${row.fileName}》，学生就业记录标记为已核验`)
        this.load()
      } else toast.error(res.message)
    },
    async onReturnConfirm({ reason }) {
      if (!this.returnTarget) return
      this.submitting = true
      try {
        const res = await api.returnMaterial(this.returnTarget.id, { reason })
        if (res.code === 0) {
          toast.success('材料已退回，原因已通知学生并留痕')
          this.returnVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'MATERIAL' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchApprove') this.batchApproveVisible = true
      if (key === 'batchReturn') this.batchReturnVisible = true
    },
    async onBatchApproveConfirm() {
      this.submitting = true
      try {
        const res = await api.batchReviewMaterials(this.selected, { pass: true })
        if (res.code === 0) {
          toast.success(`已批量通过 ${res.data.count} 份材料`)
          this.batchApproveVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onBatchReturnConfirm({ reason }) {
      this.submitting = true
      try {
        const res = await api.batchReviewMaterials(this.selected, { pass: false, reason })
        if (res.code === 0) {
          toast.success(`已批量退回 ${res.data.count} 份材料，原因已留痕`)
          this.batchReturnVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('materialList', payload)
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';
</style>
