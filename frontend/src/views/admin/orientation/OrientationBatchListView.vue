<template>
  <ModulePageShell
    title="迎新批次"
    subtitle="组织整轮迎新的时间轴与状态骨架（草稿 → 进行中 → 已结束）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="迎新批次管理"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 个批次 · 状态流转全程留痕`" @action="onToolbar" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无迎新批次" description="点击右上角「新建批次」创建本轮迎新" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-status="{ row }">
          <StatusTag :type="statusTagType[row.status] || 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-reportRange="{ row }">
          <span>{{ dateShort(row.reportStartDate) }} ~ {{ dateShort(row.reportEndDate) || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新建 / 编辑 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? '编辑迎新批次' : '新建迎新批次'"
        :fields="editFields"
        :model="editingModel"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <!-- 启用 / 结束 / 作废 二次确认 -->
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
/** /admin/orientation/batches 迎新批次（列表 / 新建 / 编辑 / 启用 / 结束 / 作废；真实走后端 /orientation/batches）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })
const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'ACTIVE', label: '进行中' },
  { value: 'CLOSED', label: '已结束' }
]

export default {
  name: 'OrientationBatchListView',
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
    EditDrawer,
    TableActionColumn,
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
      filters: EMPTY_FILTERS(),
      editVisible: false,
      editing: null,
      editingModel: null,
      confirmVisible: false,
      confirmMode: '',
      confirmRow: null,
      statusTagType: { DRAFT: 'default', ACTIVE: 'success', CLOSED: 'info' }
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
    toolbarActions() {
      return [{ key: 'create', label: '新建批次' }]
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
        { key: 'year', title: '年份' },
        { key: 'reportRange', title: '报到起止' },
        { key: 'plannedCount', title: '计划新生数' },
        { key: 'status', title: '状态' },
        { key: 'updateTime', title: '更新时间' },
        { key: 'actions', title: '操作' }
      ]
    },
    editFields() {
      return [
        { key: 'batchName', label: '批次名称', type: 'text', required: true, placeholder: '如：2026 级新生迎新' },
        { key: 'batchNo', label: '批次编号', type: 'text', required: true, placeholder: '如：ORI-2026', disabled: !!this.editing },
        { key: 'year', label: '年份', type: 'text', placeholder: '如：2026' },
        { key: 'startDate', label: '批次开始', type: 'date' },
        { key: 'endDate', label: '批次结束', type: 'date' },
        { key: 'reportStartDate', label: '报到开始', type: 'date' },
        { key: 'reportEndDate', label: '报到结束', type: 'date' },
        { key: 'plannedCount', label: '计划新生数', type: 'number' },
        { key: 'remark', label: '备注', type: 'textarea', placeholder: '批次说明（可选）' }
      ]
    },
    confirmConf() {
      const r = this.confirmRow
      if (this.confirmMode === 'activate') {
        return { title: '启用批次', message: r ? `将「${r.batchName}」置为「进行中」，新生报到流程正式开放。` : '', type: 'primary', confirmText: '确认启用', requireReason: false }
      }
      if (this.confirmMode === 'close') {
        return { title: '结束批次', message: r ? `将「${r.batchName}」置为「已结束」，结束后批次不可再编辑。` : '', type: 'danger', confirmText: '确认结束', requireReason: false }
      }
      if (this.confirmMode === 'void') {
        return { title: '作废批次', message: r ? `作废「${r.batchName}」后将从列表移除（逻辑作废，可审计）。` : '', type: 'danger', confirmText: '确认作废', requireReason: true }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    async init() {
      const ctx = await api.getOrientationContext()
      if (ctx.code === 0) this.ctx = ctx.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await api.getOrientationBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
      return v ? String(v).slice(0, 10) : ''
    },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    openCreate() {
      this.editing = null
      this.editingModel = { plannedCount: 0 }
      this.editVisible = true
    },
    openEdit(row) {
      this.editing = row
      this.editingModel = {
        batchName: row.batchName,
        batchNo: row.batchNo,
        year: row.year,
        startDate: this.dateShort(row.startDate),
        endDate: this.dateShort(row.endDate),
        reportStartDate: this.dateShort(row.reportStartDate),
        reportEndDate: this.dateShort(row.reportEndDate),
        plannedCount: row.plannedCount,
        remark: row.remark
      }
      this.editVisible = true
    },
    async onEditSubmit(form) {
      this.submitting = true
      try {
        const res = this.editing
          ? await api.updateOrientationBatch(this.editing.id, form)
          : await api.createOrientationBatch(form)
        if (res.code === 0) {
          toast.success(this.editing ? '已保存' : '已新建批次')
          this.editVisible = false
          await this.load()
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        this.submitting = false
      }
    },
    rowActions(row) {
      return [
        { key: 'edit', label: '编辑', disabled: row.status === 'CLOSED', disabledReason: row.status === 'CLOSED' ? '已结束批次不可编辑' : '' },
        { key: 'activate', label: '启用', disabled: row.status !== 'DRAFT', disabledReason: row.status !== 'DRAFT' ? '仅草稿可启用' : '' },
        { key: 'close', label: '结束', disabled: row.status !== 'ACTIVE', disabledReason: row.status !== 'ACTIVE' ? '仅进行中可结束' : '' },
        { key: 'void', label: '作废', disabled: row.status === 'ACTIVE', disabledReason: row.status === 'ACTIVE' ? '进行中批次不可作废' : '' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'edit') return this.openEdit(row)
      this.confirmMode = key
      this.confirmRow = row
      this.confirmVisible = true
    },
    async onConfirm(reason) {
      const row = this.confirmRow
      if (!row) return
      let res
      if (this.confirmMode === 'activate') res = await api.activateOrientationBatch(row.id)
      else if (this.confirmMode === 'close') res = await api.closeOrientationBatch(row.id)
      else if (this.confirmMode === 'void') res = await api.voidOrientationBatch(row.id, reason)
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
