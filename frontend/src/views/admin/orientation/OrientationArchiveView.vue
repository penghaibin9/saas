<template>
  <ModulePageShell title="迎新归档" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新归档">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`${currentBatch?.batchName || '全部批次'} · 共 ${total} 个归档任务`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <p v-if="!loading && scopeReason" class="archive-hint" role="status">{{ scopeReason }}</p>
      <p v-else-if="!loading && manageReason" class="archive-hint" role="status">{{ manageReason }}</p>
      <section v-if="currentBatch && currentBatch.status !== 'CLOSED'" class="archive-preparation">
        <p>当前批次{{ currentBatch.status === 'ACTIVE' ? '正在进行' : '尚未启用' }}。完成入学确认或未到校处理，再关闭批次，即可执行归档。</p>
        <div class="archive-links">
          <button type="button" @click="openBatchWork('qualification', currentBatch)">查看待办与入学确认</button>
          <button type="button" @click="openBatchWork('no-show', currentBatch)">处理未到校</button>
          <button type="button" @click="openBatchWork('batches', currentBatch)">前往批次管理</button>
        </div>
      </section>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无归档任务" :description="manageReason || '新建归档任务，批次关闭后执行并查看新生状态快照'" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'DONE' ? 'success' : 'warning'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <section v-if="snapshotId" class="archive-snapshots"><div class="archive-heading"><h3>归档快照</h3><button type="button" @click="closeSnapshots">关闭</button></div><p v-if="snapshotLoading">正在读取快照…</p><ErrorState v-else-if="snapshotError" :description="snapshotError" @retry="loadSnapshots" /><DataTable v-else :columns="[{ key: 'name', title: '姓名' }, { key: 'admissionNo', title: '录取编号' }, { key: 'stage', title: '办结结果' }, { key: 'archivedAt', title: '归档时间' }]" :rows="snapshots" row-key="id" :pagination="{ page: snapshotPage, pageSize: 20, total: snapshotTotal }" @page-change="p => { snapshotPage = p; loadSnapshots() }" /></section>
      <EditDrawer v-model:visible="editVisible" title="新建归档批次" :fields="editFields" :model="editingModel" :submitting="submitting" @submit="onEditSubmit" />
      <AppConfirmDialog v-model:visible="runVisible" title="执行归档" :message="runRow ? `确认执行「${runRow.archiveName}」归档？将核验本批次是否办结，并保存每名新生的状态快照。` : ''" type="primary" confirm-text="确认归档" :submitting="runSubmitting" @confirm="onRun" />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = (batchId = '') => ({ batchId, keyword: '', status: '' })

export default {
  name: 'OrientationArchiveView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, AppConfirmDialog, EditDrawer, TableActionColumn, NoPermissionState },
  data() {
    return { requestSerial: 0, actionSerial: 0, currentBatch: null, snapshotSerial: 0, snapshotLoading: false, snapshotError: '', batches: [], snapshotId: null, snapshots: [], snapshotPage: 1, snapshotTotal: 0, ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editingModel: null, runVisible: false, runSubmitting: false, runRow: null }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    batchId() { return String(this.$route.query.batchId || '') },
    noPermission() { return !!this.ctx && !this.perms['orientation.student.view']?.allowed },
    scopeReason() { return this.ctx && !['TENANT', 'TENANT_ALL', 'SCHOOL'].includes(this.ctx.dataScope?.scope) ? '批次归档和快照需由具有全校数据范围的迎新管理人员办理。' : '' },
    manageReason() {
      if (!this.ctx) return '正在读取办理权限，请稍候'
      if (this.noPermission) return '当前身份无权查看迎新归档'
      if (this.scopeReason) return this.scopeReason
      if (this.ctx.readonlyTenant) return this.ctx.readonlyReason || '当前学校处于只读状态，暂不能办理归档'
      if (!this.perms['orientation.student.edit']?.allowed) return '当前身份可查看归档列表，办理归档需要学校迎新管理权限'
      if (this.loading) return '正在读取批次信息，请稍候'
      if (this.error) return '请先重试加载归档和批次信息'
      return ''
    },
    toolbarActions() { return [{ key: 'create', label: '新建归档', disabled: !!this.manageReason, disabledReason: this.manageReason }] },
    filterFields() { return [{ key: 'batchId', label: '迎新批次', type: 'select', options: this.batches.map(b => ({ value: String(b.id), label: b.batchName })) }, { key: 'keyword', label: '关键词', type: 'text', placeholder: '归档名称' }, { key: 'status', label: '状态', type: 'select', options: [{ value: 'PENDING', label: '待归档' }, { value: 'DONE', label: '已归档' }] }] },
    tableColumns() { return [{ key: 'archiveName', title: '归档名称' }, { key: 'batchNo', title: '批次号' }, { key: 'scope', title: '范围' }, { key: 'itemCount', title: '归档数' }, { key: 'archivedBy', title: '归档人' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'archiveName', label: '归档名称', type: 'text', required: true, placeholder: '如：2026 级迎新归档' }, { key: 'batchNo', label: '迎新批次', type: 'select', required: true, disabled: !!this.currentBatch, options: this.batches.map(b => ({ value: b.batchNo, label: b.batchName || '未命名批次' })) }, { key: 'remark', label: '备注', type: 'textarea' }] }
  },
  async created() { this.filters = EMPTY_FILTERS(this.batchId); await this.load() },
  beforeUnmount() { this.requestSerial++; this.actionSerial++; this.closeSnapshots() },
  watch: {
    '$route.query.batchId'() {
      this.page = 1; this.filters = EMPTY_FILTERS(this.batchId)
      this.actionSerial++; this.submitting = false; this.runSubmitting = false
      this.editVisible = false; this.editingModel = null; this.runVisible = false; this.runRow = null
      this.closeSnapshots()
      return this.load()
    }
  },
  methods: {
    async load() {
      const serial = ++this.requestSerial
      const batchId = this.batchId
      this.loading = true; this.error = ''; this.rows = []; this.total = 0; this.currentBatch = null; this.batches = []; this.ctx = null
      this.closeSnapshots()
      try {
        const c = await api.getOrientationContext()
        if (serial !== this.requestSerial) return
        if (c.code !== 0) throw new Error(c.message || '迎新权限读取失败')
        this.ctx = c.data
        if (this.noPermission) return
        const [batches, batch, res] = await Promise.all([
          api.getOrientationBatches({ pageSize: 200 }),
          batchId ? api.getOrientationBatch(batchId) : Promise.resolve(null),
          api.getArchives({ ...this.filters, batchId: batchId || undefined, page: this.page, pageSize: this.pageSize })
        ])
        if (serial !== this.requestSerial) return
        if (batches.code !== 0 || (batch && batch.code !== 0) || res.code !== 0) throw new Error(batch?.code ? batch.message : batches.code ? batches.message : res.message)
        this.currentBatch = batch?.data || null
        this.batches = batches.data.list
        if (this.currentBatch) this.batches = [this.currentBatch, ...this.batches.filter(b => String(b.id) !== batchId)]
        this.rows = res.data.list; this.total = res.data.total
      } catch (e) { if (serial === this.requestSerial) this.error = e.message || '归档和批次信息加载失败' }
      finally { if (serial === this.requestSerial) this.loading = false }
    },
    search() {
      this.page = 1
      if (String(this.filters.batchId || '') !== this.batchId) return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, batchId: this.filters.batchId || '' } })
      return this.load()
    },
    reset() { this.filters = EMPTY_FILTERS(this.batchId); this.page = 1; return this.load() },
    turnPage(p) { this.page = p; return this.load() },
    onToolbar(k) {
      if (k !== 'create') return
      if (this.manageReason) return toast.error(this.manageReason)
      this.editingModel = this.currentBatch ? { batchNo: this.currentBatch.batchNo, archiveName: `${this.currentBatch.batchName}归档` } : {}
      this.editVisible = true
    },
    batchFor(row) {
      if (row.batchId && row.batchStatus) return { id: String(row.batchId), status: row.batchStatus, batchName: row.batchName, batchNo: row.batchNo }
      return this.batches.find(b => b.batchNo === row.batchNo) || null
    },
    runReason(row) {
      if (this.manageReason) return this.manageReason
      const batch = this.batchFor(row)
      if (!batch) return '无法确认归档所属批次，请重新加载后再办理'
      return batch.status === 'CLOSED' ? '' : '请先完成入学确认或未到校处理，并关闭本批次'
    },
    rowActions(row) {
      if (row.status === 'DONE') return [{ key: 'view', label: '查看快照', disabled: !!this.scopeReason, disabledReason: this.scopeReason }]
      const reason = this.runReason(row)
      const actions = [{ key: 'run', label: '执行归档', disabled: !!reason, disabledReason: reason }]
      const batch = this.batchFor(row)
      if (batch && batch.status !== 'CLOSED') actions.push({ key: 'prepare', label: '办理批次收尾' })
      return actions
    },
    onRowAction(k, row) {
      if (k === 'prepare') return this.openBatchWork('batches', this.batchFor(row))
      if (k === 'view') {
        if (this.scopeReason) return toast.error(this.scopeReason)
        this.snapshotId = row.id; this.snapshotPage = 1; return this.loadSnapshots()
      }
      if (k === 'run') {
        const reason = this.runReason(row)
        if (reason) return toast.error(reason)
        this.runRow = row; this.runVisible = true
      }
    },
    openBatchWork(page, batch) {
      if (!batch?.id) return
      return this.$router.push({ path: `/admin/orientation/${page}`, query: { batchId: String(batch.id), ...(page === 'batches' ? { panel: 'settings' } : {}) } })
    },
    closeSnapshots() { this.snapshotSerial++; this.snapshotId = null; this.snapshots = []; this.snapshotTotal = 0; this.snapshotLoading = false; this.snapshotError = '' },
    async loadSnapshots() {
      if (!this.snapshotId) return
      const serial = ++this.snapshotSerial
      this.snapshotLoading = true; this.snapshotError = ''; this.snapshots = []; this.snapshotTotal = 0
      try {
        const r = await api.getArchiveItems(this.snapshotId, { page: this.snapshotPage, pageSize: 20 })
        if (serial !== this.snapshotSerial) return
        if (r.code !== 0) throw new Error(r.message || '读取快照失败')
        this.snapshots = r.data.list.map(s => ({ ...s, stage: ({ ENROLLED: '已入学', NO_SHOW: '未到校', CANCELLED: '取消入学' })[s.stage] || '状态待核对' }))
        this.snapshotTotal = r.data.total
      } catch (e) { if (serial === this.snapshotSerial) this.snapshotError = e.message || '读取快照失败' }
      finally { if (serial === this.snapshotSerial) this.snapshotLoading = false }
    },
    async onEditSubmit(form) {
      if (this.submitting) return
      if (this.manageReason) return toast.error(this.manageReason)
      const serial = this.actionSerial
      this.submitting = true
      try {
        const res = await api.createArchive({ ...form, ...(this.currentBatch ? { batchNo: this.currentBatch.batchNo } : {}) })
        if (serial !== this.actionSerial) return
        if (res.code === 0) { toast.success('归档任务已创建，批次关闭后可执行归档'); this.editVisible = false; await this.load() }
        else toast.error(res.message || '保存失败')
      } catch (e) { if (serial === this.actionSerial) toast.error(e.message || '保存失败') }
      finally { if (serial === this.actionSerial) this.submitting = false }
    },
    async onRun() {
      if (this.runSubmitting || !this.runRow) return
      const reason = this.runReason(this.runRow)
      if (reason) return toast.error(reason)
      const serial = this.actionSerial
      this.runSubmitting = true
      try {
        const res = await api.runArchive(this.runRow.id)
        if (serial !== this.actionSerial) return
        if (res.code === 0) { toast.success(`已归档 ${res.data.itemCount} 名新生，可查看归档快照`); this.runVisible = false; await this.load() }
        else toast.error(res.message || '归档失败')
      } catch (e) { if (serial === this.actionSerial) toast.error(e.message || '归档失败') }
      finally { if (serial === this.actionSerial) this.runSubmitting = false }
    }
  }
}
</script>

<style scoped>
.archive-snapshots { margin-top:24px; border-top:1px solid var(--border-color); padding-top:16px; }
.archive-heading { display:flex; justify-content:space-between; align-items:center; }
.archive-hint, .archive-preparation { color: var(--text-secondary); }
.archive-preparation { padding: 12px 16px; border: 1px solid var(--border-color); border-radius: var(--radius-base); margin: 12px 0; }
.archive-preparation p { margin: 0 0 8px; }
.archive-links { display: flex; flex-wrap: wrap; gap: 12px; }
.archive-links button { color: var(--primary-600); border: 0; background: transparent; padding: 4px 0; cursor: pointer; }
</style>
