<template>
  <ModulePageShell title="迎新归档"  watermark-purpose="迎新归档">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[{ key: 'create', label: '新建归档' }]" :hint="`共 ${total} 个归档批次`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无归档批次" description="点击右上角「新建归档」创建" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'DONE' ? 'success' : 'warning'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <section v-if="snapshotId" class="archive-snapshots"><div class="archive-heading"><h3>归档快照</h3><button type="button" @click="snapshotId = null">关闭</button></div><p v-if="snapshotLoading">正在读取快照…</p><p v-if="snapshotError" role="alert">{{ snapshotError }}</p><DataTable v-if="!snapshotLoading" :columns="[{ key: 'name', title: '姓名' }, { key: 'admissionNo', title: '录取编号' }, { key: 'stage', title: '办结结果' }, { key: 'archivedAt', title: '归档时间' }]" :rows="snapshots" row-key="id" :pagination="{ page: snapshotPage, pageSize: 20, total: snapshotTotal }" @page-change="p => { snapshotPage = p; loadSnapshots() }" /></section>
      <EditDrawer v-model:visible="editVisible" title="新建归档批次" :fields="editFields" :model="editingModel" :submitting="submitting" @submit="onEditSubmit" />
      <AppConfirmDialog v-model:visible="runVisible" title="执行归档" :message="runRow ? `确认执行「${runRow.archiveName}」归档？将核验本批次是否办结，并保存每名新生的状态快照。` : ''" type="primary" confirm-text="确认归档" @confirm="onRun" />
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
  name: 'OrientationArchiveView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, AppConfirmDialog, EditDrawer, TableActionColumn, NoPermissionState },
  data() {
    return { snapshotSerial: 0, snapshotLoading: false, snapshotError: '', batches: [], snapshotId: null, snapshots: [], snapshotPage: 1, snapshotTotal: 0, ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editingModel: null, runVisible: false, runRow: null }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '归档名称' }, { key: 'status', label: '状态', type: 'select', options: [{ value: 'PENDING', label: '待归档' }, { value: 'DONE', label: '已归档' }] }] },
    tableColumns() { return [{ key: 'archiveName', title: '归档名称' }, { key: 'batchNo', title: '批次号' }, { key: 'scope', title: '范围' }, { key: 'itemCount', title: '归档数' }, { key: 'archivedBy', title: '归档人' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'archiveName', label: '归档名称', type: 'text', required: true, placeholder: '如：2026 级迎新归档' }, { key: 'batchNo', label: '迎新批次', type: 'select', required: true, options: this.batches.map(b => ({ value: b.batchNo, label: b.batchName || '未命名批次' })) }, { key: 'remark', label: '备注', type: 'textarea' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; const b = await api.getOrientationBatches({ pageSize: 200 }); if (b.code === 0) this.batches = b.data.list; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getArchives({ ...this.filters, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(k) { if (k === 'create') { this.editingModel = {}; this.editVisible = true } },
    rowActions(row) { const done = row.status === 'DONE'; return done ? [{ key: 'view', label: '查看快照' }] : [{ key: 'run', label: '执行归档' }] },
    onRowAction(k, row) { if (k === 'view') { this.snapshotId = row.id; this.snapshotPage = 1; this.loadSnapshots(); return } if (k === 'run') { this.runRow = row; this.runVisible = true } },
    async loadSnapshots() { const serial = ++this.snapshotSerial; this.snapshotLoading = true; this.snapshotError = ''; this.snapshots = []; this.snapshotTotal = 0; const r = await api.getArchiveItems(this.snapshotId, { page: this.snapshotPage, pageSize: 20 }); if (serial !== this.snapshotSerial) return; this.snapshotLoading = false; if (r.code === 0) { this.snapshots = r.data.list.map(s => ({ ...s, stage: ({ ENROLLED: '已入学', NO_SHOW: '未到校', CANCELLED: '取消入学' })[s.stage] || '状态待核对' })); this.snapshotTotal = r.data.total } else this.snapshotError = r.message || '读取失败' },
    async onEditSubmit(form) {
      this.submitting = true
      try { const res = await api.createArchive(form); if (res.code === 0) { toast.success('已新建归档'); this.editVisible = false; await this.load() } else toast.error(res.message || '保存失败') } finally { this.submitting = false }
    },
    async onRun() { const res = await api.runArchive(this.runRow.id); if (res.code === 0) { toast.success(`已归档 ${res.data.itemCount} 名新生`); this.runVisible = false; this.load() } else toast.error(res.message || '归档失败') }
  }
}
</script>

<style scoped>
.archive-snapshots { margin-top:24px; border-top:1px solid var(--border-color); padding-top:16px; }
.archive-heading { display:flex; justify-content:space-between; align-items:center; }
</style>
