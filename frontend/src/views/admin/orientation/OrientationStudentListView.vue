<template>
  <ModulePageShell :title="fixedBatch ? `${fixedBatch.batchName} · 新生名单` : '新生名单管理'" subtitle="新增、导入新生并维护录取班级；现场报到请进入新生报到" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="新生台账查阅">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <p v-if="fixedBatch?.status === 'CLOSED'" role="status">该迎新批次已结束，名单仅供查阅。</p>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名新生 · 操作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无符合条件的新生记录" description="可调整筛选条件，或通过「新增新生记录 / 批量导入」录入数据" />
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
        <template #cell-name="{ row }">
          <b>{{ row.name }}</b>
          <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" style="margin-left: 6px" />
        </template>
        <template #cell-stage="{ row }">
          <StatusTag :type="stageTagType[row.stage] || 'default'" :label="labelOf('stage', row.stage)" />
        </template>
        <template #cell-reportStatus="{ row }">
          <StatusTag :type="reportTagType[row.reportStatus] || 'default'" :label="labelOf('reportStatus', row.reportStatus)" dot />
        </template>
        <template #cell-paymentStatus="{ row }">
          <StatusTag :type="paymentTagType[row.paymentStatus] || 'default'" :label="labelOf('paymentStatus', row.paymentStatus)" />
        </template>
        <template #cell-materialStatus="{ row }">
          <StatusTag :type="materialTagType[row.materialStatus] || 'default'" :label="labelOf('materialStatus', row.materialStatus)" />
        </template>
        <template #cell-dormStatus="{ row }">
          <StatusTag :type="dormTagType[row.dormStatus] || 'default'" :label="labelOf('dormStatus', row.dormStatus)" />
        </template>
        <template #cell-riskLevel="{ row }">
          <RiskTag :level="row.riskLevel" />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? '编辑报到信息' : '新增新生记录'"
        :fields="editFields"
        :model="editing || { batchId: filters.batchId }"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <DeleteConfirmDialog
        v-model:visible="voidVisible"
        title="作废报到记录"
        :message="voidTarget ? `确认作废「${voidTarget.name}」的报到记录？作废后不参与迎新统计。` : ''"
        :submitting="submitting"
        @confirm="onVoidConfirm"
      />

      <AppConfirmDialog
        v-model:visible="assignVisible"
        title="批量分配辅导员"
        :message="`将为选中的 ${selected.length} 名新生统一分配辅导员。`"
        type="primary"
        confirm-text="确认分配"
        :submitting="submitting"
        @confirm="onAssignConfirm"
      >
        <AppTextInput v-model="assignCounselor" placeholder="请输入辅导员姓名" />
      </AppConfirmDialog>

      <ImportDialog
        v-model:visible="importVisible"
        :template="importTemplate"
        :batch-name="fixedBatch?.batchName || ''"
        :download-template-fn="downloadImportTemplateFn"
        :validate-fn="validateImportFn"
        :import-fn="confirmImportFn"
        @imported="load"
      />
      <ExportDialog
        v-model:visible="exportVisible"
        title="导出报到台账"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 新生台账" mode="modal" size="xlarge">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 页面 2：/admin/orientation/students 新生报到学生列表。
 * 管理能力：新增 / 查看 / 编辑 / 作废 / 高级筛选 / 列设置 / 批量提醒 / 批量分配辅导员 /
 * 导入 / 导出（脱敏+水印+审计确认）/ 操作留痕 / 权限置灰 / 空·加载·异常·无权限状态。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog, AppTextInput } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import {
  TableActionColumn,
  BatchActionBar,
  EditDrawer,
  ImportDialog,
  ExportDialog,
  AuditTrailPanel,
  ColumnSettings,
  DeleteConfirmDialog,
  NoPermissionState
} from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { STAGE_TAG_TYPE, REPORT_TAG_TYPE, PAYMENT_TAG_TYPE, MATERIAL_TAG_TYPE, DORM_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ batchId: '', keyword: '', classId: '', stage: '', reportStatus: '', paymentStatus: '', riskLevel: '' })

export default {
  name: 'OrientationStudentListView',
  props: { fixedBatch: { type: Object, default: null } },
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    RiskTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppTextInput,
    AppDrawer,
    TableActionColumn,
    BatchActionBar,
    EditDrawer,
    ImportDialog,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    DeleteConfirmDialog,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true,
      requestSerial: 0,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      selected: [],
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      filterOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      batches: [],
      importTemplate: null,
      exportOpts: {},
      editVisible: false,
      editing: null,
      voidVisible: false,
      voidTarget: null,
      assignVisible: false,
      assignCounselor: '',
      importVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      stageTagType: STAGE_TAG_TYPE,
      reportTagType: REPORT_TAG_TYPE,
      paymentTagType: PAYMENT_TAG_TYPE,
      materialTagType: MATERIAL_TAG_TYPE,
      dormTagType: DORM_TAG_TYPE
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
      const p = this.perms['orientation.student.view']
      return p ? !p.allowed : false
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        ...(!this.fixedBatch ? [{ key: 'batchId', label: '迎新批次', type: 'select', options: this.batchOptions }] : []),
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
        { key: 'classId', label: '班级', type: 'select', options: this.filterOptions.classes || [] },
        { key: 'stage', label: '学生阶段', type: 'select', options: this.statusOptions.stage || [] },
        { key: 'reportStatus', label: '报到状态', type: 'select', options: this.statusOptions.reportStatus || [] },
        { key: 'paymentStatus', label: '缴费状态', type: 'select', options: this.statusOptions.paymentStatus || [] },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: this.statusOptions.riskLevel || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      return [
        this.permAction('orientation.student.create', { key: 'create', label: '新增新生记录', variant: 'primary' }),
        this.permAction('orientation.student.import', { key: 'import', label: '批量导入新生' }),
        this.permAction('orientation.student.export', { key: 'export', label: '导出报到台账' }),
        this.permAction('orientation.audit.view', { key: 'audit', label: '操作留痕' })
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
    },
    editFields() {
      return [
        { key: 'name', label: '姓名', type: 'text', required: true, disabled: !!this.editing },
        { key: 'admissionNo', label: '录取编号', type: 'text', required: true, disabled: !!this.editing },
        { key: 'batchId', label: '迎新批次', type: 'select', options: this.batchOptions, required: true, disabled: !!this.editing || !!this.fixedBatch },
        { key: 'classId', label: '录取班级（自动确定学院/专业）', type: 'remote', placeholder: '输入班级名称，如软件技术2601', remoteSearch: api.searchOrientationClasses, options: [...(this.filterOptions.classes || []), ...(this.editing?.classId ? [{ value: String(this.editing.classId), label: this.editing.className }] : [])], required: true },
        { key: 'admissionType', label: '录取类型', type: 'text' },
        { key: 'counselor', label: '辅导员', type: 'text' },
        { key: 'phone', label: '联系电话', type: 'text', placeholder: '敏感字段，列表脱敏展示' },
        { key: 'origin', label: '生源地', type: 'region' }
      ]
    },
    batchOptions() {
      return this.batches.map((row) => ({
        value: String(row.id),
        label: `${row.batchName} · ${row.batchNo}${row.status === 'CLOSED' ? '（已结束）' : ''}`,
        disabled: row.status === 'CLOSED'
      }))
    }
  },
  watch: { '$route.query.batchId'(value) { if (!this.fixedBatch && String(value || '') !== this.filters.batchId) { this.filters.batchId = String(value || ''); this.page = 1; this.load() } } },
  beforeUnmount() { ++this.requestSerial },
  async created() {
    if (this.fixedBatch) this.filters.batchId = String(this.fixedBatch.id)
    else if (this.$route.query.batchId) this.filters.batchId = String(this.$route.query.batchId)
    await this.init()
  },
  methods: {
    permAction(key, action) {
      const p = this.perms[key]
      if (p && !p.visible) return null
      const closed = this.fixedBatch?.status === 'CLOSED' && ['orientation.student.create', 'orientation.student.import'].includes(key)
      return { ...action, disabled: closed || (p ? !p.allowed : false), disabledReason: closed ? '该批次已结束，仅可查阅' : p?.reason }
    },
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || (value ? '待确认' : '—')
    },
    async init() {
      const [ctx, status, filter, cols, batch, tpl, exp, batches] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFilterOptions(),
        api.getFieldColumns('studentList'),
        api.getBatchActions('studentList'),
        api.getImportTemplate('studentList'),
        api.getExportOptions('studentList'),
        this.fixedBatch ? Promise.resolve({ code: 0, data: { list: [this.fixedBatch] } }) : api.getOrientationBatches({ page: 1, pageSize: 200 })
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (filter.code === 0) this.filterOptions = filter.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (tpl.code === 0) this.importTemplate = tpl.data
      if (exp.code === 0) this.exportOpts = exp.data
      if (batches.code === 0) this.batches = batches.data.list || []
      if (!this.filters.batchId && this.$route.query.batchId === undefined) {
        const activeBatch = this.batches.find((row) => row.status !== 'CLOSED')
        if (activeBatch) this.filters.batchId = String(activeBatch.id)
      }
      await this.search()
    },
    async load() {
      const serial = ++this.requestSerial
      if (this.fixedBatch) this.filters.batchId = String(this.fixedBatch.id)
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getOrientationStudents({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (serial !== this.requestSerial) return
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        if (serial === this.requestSerial) this.error = e.message || '加载失败'
      } finally {
        if (serial === this.requestSerial) this.loading = false
      }
    },
    async search() {
      this.page = 1
      if (!this.fixedBatch && String(this.$route.query.batchId ?? '') !== this.filters.batchId) {
        await this.$router.replace({ query: { ...this.$route.query, batchId: this.filters.batchId } })
      }
      return this.load()
    },
    reset() {
      const batchId = this.fixedBatch ? String(this.fixedBatch.id) : String(this.$route.query.batchId ?? this.filters.batchId)
      this.filters = { ...EMPTY_FILTERS(), batchId }
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    viewDetail(row) {
      this.$router.push({ path: `/admin/orientation/students/${row.id}`, query: { batchId: this.filters.batchId || undefined, from: this.fixedBatch ? 'batch' : undefined } })
    },
    rowActions(row) {
      const edit = this.perms['orientation.student.edit']
      const voidP = this.perms['orientation.student.void']
      return [
        { key: 'view', label: '详情' },
        { key: 'edit', label: '编辑', disabled: this.fixedBatch?.status === 'CLOSED' || (edit ? !edit.allowed : false), disabledReason: this.fixedBatch?.status === 'CLOSED' ? '该批次已结束，仅可查阅' : edit?.reason, visible: edit ? edit.visible : true },
        {
          key: 'void',
          label: '作废',
          danger: true,
          disabled: this.fixedBatch?.status === 'CLOSED' || (voidP ? !voidP.allowed : false) || row.recordStatus === 'VOIDED',
          disabledReason: this.fixedBatch?.status === 'CLOSED' ? '该批次已结束，仅可查阅' : row.recordStatus === 'VOIDED' ? '该记录已作废' : voidP?.reason,
          visible: voidP ? voidP.visible : true
        }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') this.viewDetail(row)
      if (key === 'edit') {
        this.editing = row
        this.editVisible = true
      }
      if (key === 'void') {
        this.voidTarget = row
        this.voidVisible = true
      }
    },
    onToolbar(key) {
      if (key === 'create') {
        this.editing = null
        this.editVisible = true
      }
      if (key === 'import') this.importVisible = true
      if (key === 'export') {
        if (!this.filters.batchId) {
          toast.error('请先在筛选条件中选择一个迎新批次，再导出该批次台账')
        } else {
          this.exportVisible = true
        }
      }
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({})
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    async onEditSubmit(form) {
      if (this.submitting) return
      if (this.fixedBatch) form = { ...form, batchId: String(this.fixedBatch.id) }
      this.submitting = true
      try {
        const res = this.editing ? await api.updateOrientationStudent(this.editing.id, Object.fromEntries(this.editFields.map(f => [f.key, form[f.key]]))) : await api.createOrientationStudent(form)
        if (res.code === 0) {
          toast.success(this.editing ? '报到信息已更新，已写入留痕' : '新生记录已新增')
          this.editVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onVoidConfirm({ reason }) {
      if (!this.voidTarget) return
      this.submitting = true
      try {
        const res = await api.voidOrientationStudent(this.voidTarget.id, { reason })
        if (res.code === 0) {
          toast.success('记录已作废（逻辑删除），原因已留痕')
          this.voidVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchRemind') this.doBatchRemind()
      if (key === 'batchAssign') {
        this.assignCounselor = ''
        this.assignVisible = true
      }
      if (key === 'batchExport') {
        if (!this.filters.batchId) toast.error('请先选择迎新批次，再导出勾选名单')
        else this.exportVisible = true
      }
    },
    async doBatchRemind() {
      const res = await api.batchRemindStudents(this.selected, '报到提醒')
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名新生发送提醒，操作已留痕`)
    },
    async onAssignConfirm() {
      if (!this.assignCounselor.trim()) {
        toast.error('请输入辅导员姓名')
        return
      }
      this.submitting = true
      try {
        const res = await api.batchAssignCounselor(this.selected, { counselor: this.assignCounselor.trim() })
        if (res.code === 0) {
          toast.success(`已为 ${res.data.count} 名新生分配辅导员`)
          this.assignVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    downloadImportTemplateFn() {
      return api.downloadImportTemplate('studentList')
    },
    validateImportFn(file) {
      return api.validateImport('studentList', file, this.fixedBatch?.id || this.filters.batchId)
    },
    confirmImportFn(payload) {
      return api.confirmImport('studentList', payload)
    },
    exportFn(payload) {
      return api.createExport('studentList', { ...payload, batchId: this.filters.batchId })
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';

.ori-assign-input {
  width: 100%;
  height: 36px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
</style>
