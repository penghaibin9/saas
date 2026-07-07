<template>
  <ModulePageShell title="现场报到点" subtitle="迎新现场报到工位/接待点的设置与启停" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="报到点管理">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[{ key: 'create', label: '新增报到点' }]" :hint="`共 ${total} 个报到点`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无报到点" description="点击右上角「新增报到点」创建" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <EditDrawer v-model:visible="editVisible" :title="editing ? '编辑报到点' : '新增报到点'" :fields="editFields" :model="editingModel" :submitting="submitting" @submit="onEditSubmit" />
      <AppConfirmDialog v-model:visible="delVisible" title="删除报到点" :message="delRow ? `确认删除「${delRow.name}」？` : ''" type="danger" confirm-text="确认删除" @confirm="onDelete" />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'OrientationCheckinPointView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, AppConfirmDialog, EditDrawer, TableActionColumn, NoPermissionState },
  data() {
    return { ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editing: null, editingModel: null, delVisible: false, delRow: null }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '名称 / 地点' }, { key: 'status', label: '状态', type: 'select', options: [{ value: 'ENABLED', label: '启用' }, { value: 'DISABLED', label: '停用' }] }] },
    tableColumns() { return [{ key: 'name', title: '报到点' }, { key: 'location', title: '地点' }, { key: 'capacity', title: '容量' }, { key: 'inCharge', title: '负责人' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'name', label: '报到点名称', type: 'text', required: true }, { key: 'location', label: '地点', type: 'text' }, { key: 'capacity', label: '接待容量', type: 'number' }, { key: 'inCharge', label: '负责人', type: 'text' }, { key: 'remark', label: '备注', type: 'textarea' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getCheckinPoints({ ...this.filters, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(k) { if (k === 'create') { this.editing = null; this.editingModel = { capacity: 0 }; this.editVisible = true } },
    rowActions(row) { return [{ key: 'edit', label: '编辑' }, { key: 'toggle', label: row.status === 'ENABLED' ? '停用' : '启用' }, { key: 'delete', label: '删除' }] },
    async onRowAction(k, row) {
      if (k === 'edit') { this.editing = row; this.editingModel = { name: row.name, location: row.location, capacity: row.capacity, inCharge: row.inCharge, remark: row.remark }; this.editVisible = true; return }
      if (k === 'toggle') { const r = await api.toggleCheckinPoint(row.id); if (r.code === 0) { toast.success('已切换'); this.load() } else toast.error(r.message); return }
      if (k === 'delete') { this.delRow = row; this.delVisible = true }
    },
    async onEditSubmit(form) {
      this.submitting = true
      try { const res = this.editing ? await api.updateCheckinPoint(this.editing.id, form) : await api.createCheckinPoint(form); if (res.code === 0) { toast.success('已保存'); this.editVisible = false; await this.load() } else toast.error(res.message || '保存失败') } finally { this.submitting = false }
    },
    async onDelete() { const r = await api.deleteCheckinPoint(this.delRow.id); if (r.code === 0) { toast.success('已删除'); this.delVisible = false; this.load() } else toast.error(r.message) }
  }
}
</script>
