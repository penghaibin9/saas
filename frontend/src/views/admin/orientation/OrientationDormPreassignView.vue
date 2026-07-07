<template>
  <ModulePageShell title="宿舍预分配" subtitle="报到前给新生预分配楼栋/房间（分配后进入宿舍入住确认环节）" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="宿舍预分配">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生 · 预分配全程留痕`" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无新生" description="当前数据范围内没有匹配的新生" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-dormStatus="{ row }">
          <StatusTag :type="dormTagType[row.dormStatus] || 'default'" :label="row.dormStatusLabel" dot />
        </template>
        <template #cell-room="{ row }">
          <span :class="{ 'odp-muted': !row.room }">{{ row.building ? row.building + ' ' + (row.room || '') : '未分配' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions()" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <EditDrawer v-model:visible="editVisible" :title="`预分配宿舍 · ${editing ? editing.name : ''}`" :fields="editFields" :model="editingModel" :submitting="submitting" @submit="onEditSubmit" />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', dormStatus: 'UNASSIGNED' })

export default {
  name: 'OrientationDormPreassignView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, EditDrawer, TableActionColumn, NoPermissionState },
  data() {
    return { ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editing: null, editingModel: null, dormTagType: { UNASSIGNED: 'warning', ASSIGNED: 'primary', CHECKED_IN: 'success', EXCEPTION: 'danger' } }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' }, { key: 'dormStatus', label: '宿舍状态', type: 'select', options: [{ value: 'UNASSIGNED', label: '未分配' }, { value: 'ASSIGNED', label: '已分配' }, { value: 'CHECKED_IN', label: '已入住' }] }] },
    tableColumns() { return [{ key: 'name', title: '姓名' }, { key: 'className', title: '班级' }, { key: 'room', title: '楼栋/房间' }, { key: 'dormStatus', title: '宿舍状态' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'building', label: '楼栋', type: 'text', required: true, placeholder: '如：梧桐苑 1 号楼' }, { key: 'room', label: '房间/床位', type: 'text', required: true, placeholder: '如：1-301-1' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getDormitoryCheckinList({ ...this.filters, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions() { return [{ key: 'assign', label: '预分配' }] },
    onRowAction(k, row) { if (k === 'assign') { this.editing = row; this.editingModel = { building: row.building, room: row.room }; this.editVisible = true } },
    async onEditSubmit(form) {
      this.submitting = true
      try { const res = await api.updateDormInfo(this.editing.id, { ...form, dormStatus: 'ASSIGNED' }); if (res.code === 0) { toast.success('已预分配'); this.editVisible = false; await this.load() } else toast.error(res.message || '分配失败') } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.odp-muted {
  color: var(--t3);
}
</style>
