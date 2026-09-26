<template>
  <ModulePageShell flat title="新生宿舍安排" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="宿舍预分配">
    <template #actions>
      <AppButton variant="secondary" @click="$router.push('/admin/student-affairs/dorm/resource')">查看房态</AppButton>
      <AppButton @click="openAllocation($route.query.batchId)">自动分配 / 分配计划</AppButton>
    </template>
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生 · 按迎新批次生成分配方案，核对后发布`" />
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
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import { AppButton } from '@/components/ui'
import * as api from '@/modules/orientation/api/orientation.api'

const EMPTY_FILTERS = () => ({ keyword: '', dormStatus: 'UNASSIGNED' })

export default {
  name: 'OrientationDormPreassignView',
  components: { AppButton, ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, TableActionColumn, NoPermissionState },
  data() {
    return { ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editing: null, editingModel: null, dormTagType: { UNASSIGNED: 'warning', ASSIGNED: 'primary', CHECKED_IN: 'success', EXCEPTION: 'danger' } }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' }, { key: 'dormStatus', label: '宿舍状态', type: 'select', options: [{ value: 'UNASSIGNED', label: '未分配' }, { value: 'ASSIGNED', label: '已预留 · 待入住' }, { value: 'CHECKED_IN', label: '已入住' }] }] },
    tableColumns() { return [{ key: 'name', title: '姓名' }, { key: 'className', title: '班级' }, { key: 'room', title: '楼栋/房间' }, { key: 'dormStatus', title: '宿舍状态' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'building', label: '楼栋', type: 'text', required: true, placeholder: '如：梧桐苑 1 号楼' }, { key: 'room', label: '房间/床位', type: 'text', required: true, placeholder: '如：1-301-1' }] }
  },
  async created() { if (this.$route.query.orientationStudentId) this.filters.dormStatus = ''; const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getDormitoryCheckinList({ ...this.filters, batchId: this.$route.query.batchId || undefined, orientationStudentId: this.$route.query.orientationStudentId || undefined, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions(row) { return [{ key: 'assign', label: row.bedId ? '查看床位' : '分配计划' }] },
    onRowAction(k, row) { if (k !== 'assign') return; if (row.bedId) this.$router.push({ path: '/admin/student-affairs/dorm/resource', query: { buildingId: row.buildingId, roomId: row.roomId, bedId: row.bedId } }); else this.openAllocation(row.batchId) },
    openAllocation(batchId) { this.$router.push({ path: '/admin/student-affairs/dorm/allocation', query: { source: 'orientation', ...(typeof batchId === 'string' ? { orientationBatchId: batchId } : {}) } }) }
  }
}
</script>

<style scoped>
.odp-muted {
  color: var(--t3);
}
</style>
