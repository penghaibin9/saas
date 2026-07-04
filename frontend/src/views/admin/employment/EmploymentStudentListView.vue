<template>
  <ModulePageShell title="就业学生列表" subtitle="就业去向台账 · 敏感字段默认脱敏展示" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业台账查阅">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 条 · 操作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无符合条件的就业记录" description="可调整筛选条件，或通过「新增就业记录 / 批量导入」录入数据" />
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
        <template #cell-destinationType="{ row }">
          <StatusTag :type="destinationTagType[row.destinationType] || 'default'" :label="labelOf('destinationType', row.destinationType)" dot />
        </template>
        <template #cell-verifyStatus="{ row }">
          <StatusTag :type="verifyTagType[row.verifyStatus] || 'default'" :label="labelOf('verifyStatus', row.verifyStatus)" />
        </template>
        <template #cell-materialStatus="{ row }">
          <StatusTag :type="materialTagType[row.materialStatus] || 'default'" :label="labelOf('materialStatus', row.materialStatus)" />
        </template>
        <template #cell-helpLevel="{ row }">
          <RiskTag v-if="row.helpLevel === 'KEY_HELP'" level="HIGH" label="重点帮扶" />
          <span v-else class="emp-inline-note">常规</span>
        </template>
        <template #cell-name="{ row }">
          <b>{{ row.name }}</b>
          <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" style="margin-left: 6px" />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新增 / 编辑 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? '编辑就业信息' : '新增就业记录'"
        :fields="editFields"
        :model="editing"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <!-- 作废（逻辑删除） -->
      <DeleteConfirmDialog
        v-model:visible="voidVisible"
        title="作废就业记录"
        :message="voidTarget ? `确认作废「${voidTarget.name}」的就业记录？作废后不参与就业统计。` : ''"
        :submitting="submitting"
        @confirm="onVoidConfirm"
      />

      <!-- 批量标记去向 -->
      <AppConfirmDialog
        v-model:visible="markVisible"
        title="批量标记去向"
        :message="`将为选中的 ${selected.length} 名学生统一标记去向（标记后进入待核验）。`"
        type="primary"
        confirm-text="确认标记"
        :submitting="submitting"
        @confirm="onMarkConfirm"
      >
        <select v-model="markDestination" class="emp-mark-select">
          <option value="">请选择去向类型</option>
          <option v-for="o in statusOptions.destinationType || []" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </AppConfirmDialog>

      <ImportDialog v-model:visible="importVisible" :template="importTemplate" :validate-fn="validateImportFn" :import-fn="confirmImportFn" @imported="load" />
      <ExportDialog
        v-model:visible="exportVisible"
        title="导出就业台账"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <!-- 操作留痕 -->
      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 就业台账">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 页面 2：/admin/employment/students 就业学生列表。
 * 管理能力：新增 / 查看 / 编辑 / 作废 / 高级筛选 / 列设置 / 批量提醒 / 批量标记去向 /
 * 导入 / 导出（脱敏+水印+审计确认）/ 操作留痕 / 权限置灰 / 空·加载·异常·无权限状态。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
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
} from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { DESTINATION_TAG_TYPE, VERIFY_TAG_TYPE, MATERIAL_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', destinationType: '', verifyStatus: '', helpLevel: '' })

export default {
  name: 'EmploymentStudentListView',
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
      importTemplate: null,
      exportOpts: {},
      editVisible: false,
      editing: null,
      voidVisible: false,
      voidTarget: null,
      markVisible: false,
      markDestination: '',
      importVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      destinationTagType: DESTINATION_TAG_TYPE,
      verifyTagType: VERIFY_TAG_TYPE,
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
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 单位' },
        { key: 'classId', label: '班级', type: 'select', options: this.filterOptions.classes || [] },
        { key: 'destinationType', label: '去向类型', type: 'select', options: this.statusOptions.destinationType || [] },
        { key: 'verifyStatus', label: '核验状态', type: 'select', options: this.statusOptions.verifyStatus || [] },
        { key: 'helpLevel', label: '帮扶级别', type: 'select', options: this.statusOptions.helpLevel || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      return [
        this.permAction('employment.record.create', { key: 'create', label: '新增就业记录', variant: 'primary' }),
        this.permAction('employment.record.import', { key: 'import', label: '批量导入' }),
        this.permAction('employment.record.export', { key: 'export', label: '导出台账' }),
        this.permAction('employment.audit.view', { key: 'audit', label: '操作留痕' })
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
        { key: 'studentNo', label: '学号', type: 'text', required: true, disabled: !!this.editing },
        { key: 'classId', label: '班级', type: 'select', options: this.filterOptions.classes || [], required: true },
        { key: 'destinationType', label: '去向类型', type: 'select', options: this.statusOptions.destinationType || [], required: true },
        { key: 'companyName', label: '单位 / 院校', type: 'text', placeholder: '签约单位或升学院校' },
        { key: 'jobTitle', label: '岗位 / 专业', type: 'text' },
        { key: 'salaryRange', label: '薪资区间', type: 'text', placeholder: '如 5k-7k（敏感字段，列表脱敏展示）' },
        { key: 'signDate', label: '签约 / 确认时间', type: 'date' },
        { key: 'phone', label: '联系电话', type: 'text', placeholder: '敏感字段，列表脱敏展示' }
      ]
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    permAction(key, action) {
      const p = this.perms[key]
      if (p && !p.visible) return null
      return { ...action, disabled: p ? !p.allowed : false, disabledReason: p?.reason }
    },
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    async init() {
      const [ctx, status, filter, cols, batch, tpl, exp] = await Promise.all([
        api.getEmploymentContext(),
        api.getStatusOptions(),
        api.getFilterOptions(),
        api.getFieldColumns('studentList'),
        api.getBatchActions('studentList'),
        api.getImportTemplate('studentList'),
        api.getExportOptions('studentList')
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
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getEmploymentStudents({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
      this.$router.push(`/admin/employment/students/${row.id}`)
    },
    rowActions(row) {
      const edit = this.perms['employment.record.edit']
      const voidP = this.perms['employment.record.void']
      return [
        { key: 'view', label: '详情' },
        { key: 'edit', label: '编辑', disabled: edit ? !edit.allowed : false, disabledReason: edit?.reason, visible: edit ? edit.visible : true },
        {
          key: 'void',
          label: '作废',
          danger: true,
          disabled: (voidP ? !voidP.allowed : false) || row.recordStatus === 'VOIDED',
          disabledReason: row.recordStatus === 'VOIDED' ? '该记录已作废' : voidP?.reason,
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
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({})
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    async onEditSubmit(form) {
      this.submitting = true
      try {
        const res = this.editing ? await api.updateEmploymentRecord(this.editing.id, form) : await api.createEmploymentRecord(form)
        if (res.code === 0) {
          toast.success(this.editing ? '就业信息已更新，已写入留痕' : '就业记录已新增，进入待核验')
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
        const res = await api.voidEmploymentRecord(this.voidTarget.id, { reason })
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
      if (key === 'batchMarkStatus') {
        this.markDestination = ''
        this.markVisible = true
      }
      if (key === 'batchExport') this.exportVisible = true
    },
    async doBatchRemind() {
      const res = await api.batchRemindStudents(this.selected)
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生发送提醒，操作已留痕`)
    },
    async onMarkConfirm() {
      if (!this.markDestination) {
        toast.error('请先选择去向类型')
        return
      }
      this.submitting = true
      try {
        const res = await api.batchMarkDestination(this.selected, this.markDestination)
        if (res.code === 0) {
          toast.success(`已批量标记 ${res.data.count} 名学生去向`)
          this.markVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    validateImportFn(fileName) {
      return api.validateImport('studentList', fileName)
    },
    confirmImportFn(payload) {
      return api.confirmImport('studentList', payload)
    },
    exportFn(payload) {
      return api.createExport('studentList', payload)
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-mark-select {
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
