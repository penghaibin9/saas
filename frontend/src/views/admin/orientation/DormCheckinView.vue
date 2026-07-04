<template>
  <ModulePageShell title="宿舍入住确认" subtitle="宿舍分配 · 入住确认 · 异常标记" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="宿舍入住管理">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名新生 · 操作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无住宿数据" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-room="{ row }">{{ row.room || '未分配' }}</template>
        <template #cell-building="{ row }">{{ row.building || '未分配' }}</template>
        <template #cell-dormStatus="{ row }">
          <StatusTag :type="dormTagType[row.dormStatus] || 'default'" :label="labelOf('dormStatus', row.dormStatus)" dot />
        </template>
        <template #cell-checkinTime="{ row }">{{ row.checkinTime || '—' }}</template>
        <template #cell-exceptionNote="{ row }">
          <span class="ori-inline-note">{{ row.exceptionNote || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 编辑宿舍信息 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? `编辑宿舍信息 · ${editing.name}` : '编辑宿舍信息'"
        :fields="editFields"
        :model="editing"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <!-- 批量确认入住 -->
      <AppConfirmDialog
        v-model:visible="confirmVisible"
        title="批量确认入住"
        :message="`确认选中的 ${selected.length} 名新生已完成宿舍入住？（入住异常学生将被跳过）`"
        type="primary"
        confirm-text="确认入住"
        :submitting="submitting"
        @confirm="onBatchConfirm"
      />

      <!-- 异常标记 -->
      <AppConfirmDialog
        v-model:visible="exceptionVisible"
        title="标记入住异常"
        :message="exceptionTarget ? `将「${exceptionTarget.name}」的宿舍状态标记为入住异常。` : ''"
        type="danger"
        confirm-text="确认标记"
        require-reason
        reason-label="异常说明"
        reason-placeholder="如床位冲突 / 特殊住宿需求 / 未按时入住等（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onExceptionConfirm"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出住宿名单"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 宿舍入住">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 7：/admin/orientation/dorm 宿舍入住确认（查看 / 编辑宿舍 / 批量确认 / 异常标记 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { TableActionColumn, BatchActionBar, EditDrawer, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { DORM_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', dormStatus: '', building: '' })

export default {
  name: 'DormCheckinView',
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
    EditDrawer,
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
      filterOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      editVisible: false,
      editing: null,
      confirmVisible: false,
      exceptionVisible: false,
      exceptionTarget: null,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
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
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 房间号' },
        { key: 'dormStatus', label: '入住状态', type: 'select', options: this.statusOptions.dormStatus || [] },
        { key: 'building', label: '楼栋', type: 'select', options: this.filterOptions.buildings || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.dorm.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出住宿名单', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
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
        {
          key: 'building',
          label: '楼栋',
          type: 'select',
          required: true,
          options: (this.filterOptions.buildings || []).map((b) => ({ value: b.label, label: b.label }))
        },
        { key: 'room', label: '房间 / 床位', type: 'text', required: true, placeholder: '如 1-302-2' },
        {
          key: 'dormStatus',
          label: '入住状态',
          type: 'select',
          options: this.statusOptions.dormStatus || []
        }
      ]
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
      const [ctx, status, filter, cols, batch, exp] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFilterOptions(),
        api.getFieldColumns('dormList'),
        api.getBatchActions('dormList'),
        api.getExportOptions('dormList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (filter.code === 0) this.filterOptions = filter.data
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
        const res = await api.getDormitoryCheckinList({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
    rowActions(row) {
      const edit = this.perms['orientation.dorm.edit']
      const mark = this.perms['orientation.dorm.markException']
      return [
        { key: 'view', label: '入住信息' },
        { key: 'edit', label: '编辑宿舍', disabled: edit ? !edit.allowed : false, disabledReason: edit?.reason },
        {
          key: 'exception',
          label: '异常标记',
          danger: true,
          disabled: (mark ? !mark.allowed : false) || row.dormStatus === 'EXCEPTION',
          disabledReason: row.dormStatus === 'EXCEPTION' ? '该生已标记异常' : mark?.reason
        }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'edit') {
        this.editing = row
        this.editVisible = true
      }
      if (key === 'exception') {
        this.exceptionTarget = row
        this.exceptionVisible = true
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'DORM' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchConfirm') this.confirmVisible = true
      if (key === 'batchExport') this.exportVisible = true
    },
    async onBatchConfirm() {
      this.submitting = true
      try {
        const res = await api.batchConfirmCheckin(this.selected)
        if (res.code === 0) {
          toast.success(`已批量确认 ${res.data.count} 名新生入住，操作已留痕`)
          this.confirmVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onEditSubmit(form) {
      if (!this.editing) return
      this.submitting = true
      try {
        const res = await api.updateDormInfo(this.editing.id, form)
        if (res.code === 0) {
          toast.success('宿舍信息已更新，已写入留痕')
          this.editVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onExceptionConfirm({ reason }) {
      if (!this.exceptionTarget) return
      this.submitting = true
      try {
        const res = await api.markDormException(this.exceptionTarget.id, { note: reason })
        if (res.code === 0) {
          toast.success('已标记入住异常，说明已留痕')
          this.exceptionVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('dormList', payload)
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';
</style>
