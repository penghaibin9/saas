<template>
  <section v-if="rosterBatchId" class="ob-roster">
    <header class="ob-roster-header">
      <button type="button" @click="$router.push('/admin/orientation/batches')">‹ 返回批次列表</button>
      <span>批次设置 → 新生名单 → 信息核验 → 报到办理</span>
      <button v-if="rosterBatch" type="button" @click="$router.push({ path: '/admin/orientation/verify', query: { batchId: rosterBatchId } })">下一步：信息核验</button>
    </header>
    <LoadingState v-if="rosterLoading" />
    <ErrorState v-else-if="rosterError" :description="rosterError" @retry="loadRosterBatch" />
    <OrientationStudentListView v-else-if="rosterBatch" :fixed-batch="rosterBatch" />
  </section>
  <ModulePageShell
    v-else
    title="迎新批次与新生名单"
    subtitle="先创建批次，在批次内新增或导入新生、维护录取班级，再进入核验与报到"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="迎新批次管理"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="settingsBatchId ? '当前批次 · 状态流转全程留痕' : `共 ${total} 个批次 · 状态流转全程留痕`" @action="onToolbar" />

      <div v-if="settingsBatchId" class="ob-current-batch">
        <span>{{ rows[0]?.batchName ? `当前批次：${rows[0].batchName}` : '当前批次信息尚未读取' }}。办结新生事项后结束批次，再继续归档。</span>
        <button type="button" @click="showAllBatches">查看全部批次</button>
      </div>
      <AdvancedFilter v-else v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="init" />
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
        :submitting="confirmSubmitting"
        reason-label="作废原因（≥5 字）"
        @confirm="onConfirm"
      />

      <AppConfirmDialog
        v-model:visible="numberingVisible"
        title="一键批量生成学号"
        :message="numberingRow ? `为「${numberingRow.batchName}」中尚未分配学号的新生按名单顺序一次性编号；已有学号不会改动。` : ''"
        type="primary"
        confirm-text="确认批量生成"
        :confirm-disabled="!numberingForm.prefix.trim()"
        :submitting="numberingSubmitting"
        @confirm="onNumberingConfirm"
      >
        <div class="ob-numbering-grid">
          <label>学号前缀<AppTextInput v-model="numberingForm.prefix" placeholder="如 2026YX" /></label>
          <label>起始序号<AppTextInput v-model="numberingForm.startNumber" type="number" placeholder="1" /></label>
          <label>序号位数<AppTextInput v-model="numberingForm.width" type="number" placeholder="4" /></label>
        </div>
        <small class="ob-numbering-note">适用于万人名单：一次提交整批完成，不需要逐个新生操作。</small>
      </AppConfirmDialog>
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/batches 迎新批次（列表 / 新建 / 编辑 / 启用 / 结束 / 作废；真实走后端 /orientation/batches）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog, AppTextInput } from '@/components/common'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'
import OrientationStudentListView from './OrientationStudentListView.vue'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })
const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'ACTIVE', label: '进行中' },
  { value: 'CLOSED', label: '已结束' }
]

export default {
  name: 'OrientationBatchListView',
  components: {
    OrientationStudentListView,
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppTextInput,
    EditDrawer,
    TableActionColumn,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      requestSerial: 0,
      rosterSerial: 0,
      actionSerial: 0,
      rosterBatch: null,
      rosterLoading: false,
      rosterError: '',
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
      confirmSubmitting: false,
      numberingVisible: false,
      numberingRow: null,
      numberingSubmitting: false,
      numberingForm: { prefix: '', startNumber: 1, width: 4 },
      statusTagType: { DRAFT: 'default', ACTIVE: 'success', CLOSED: 'info' }
    }
  },
  computed: {
    rosterBatchId() { return this.$route.query.panel === 'students' ? String(this.$route.query.batchId || '') : '' },
    settingsBatchId() { return this.$route.query.panel === 'settings' ? String(this.$route.query.batchId || '') : '' },
    batchContextKey() { return `${this.$route.query.panel || ''}:${this.$route.query.batchId || ''}` },
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
        return { title: '结束批次', message: r ? `确认「${r.batchName}」的新生均已完成入学确认或未到校处理。结束后批次不可再编辑，可继续归档；仍有未办结事项时，系统会保留本批次并说明原因。` : '', type: 'danger', confirmText: '确认结束', requireReason: false }
      }
      if (this.confirmMode === 'refreshFlow') {
        return { title: '采用最新报到流程', message: r ? `仅当「${r.batchName}」尚无新生时，才会改用最新的标准流程；已有新生或已结束批次会被服务器拒绝。` : '', type: 'primary', confirmText: '确认采用最新流程', requireReason: false }
      }
      if (this.confirmMode === 'void') {
        return { title: '作废批次', message: r ? `作废「${r.batchName}」后将从列表移除（逻辑作废，可审计）。` : '', type: 'danger', confirmText: '确认作废', requireReason: true }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    }
  },
  async created() {
    if (this.rosterBatchId) await this.loadRosterBatch()
    else await this.init()
  },
  beforeUnmount() { this.requestSerial++; this.rosterSerial++; this.actionSerial++ },
  watch: {
    batchContextKey() {
      this.requestSerial++; this.rosterSerial++; this.actionSerial++
      this.rows = []; this.total = 0; this.rosterBatch = null; this.ctx = null
      this.page = 1; this.filters = EMPTY_FILTERS()
      this.confirmVisible = false; this.confirmRow = null; this.confirmMode = ''; this.confirmSubmitting = false
      this.editVisible = false; this.editing = null; this.editingModel = null; this.submitting = false
      this.numberingVisible = false; this.numberingRow = null; this.numberingSubmitting = false
      return this.rosterBatchId ? this.loadRosterBatch() : this.init()
    }
  },
  methods: {
    async loadRosterBatch() {
      const serial = ++this.rosterSerial
      const id = this.rosterBatchId
      this.rosterLoading = true; this.rosterError = ''; this.rosterBatch = null
      try {
        const res = await api.getOrientationBatch(id)
        if (serial !== this.rosterSerial) return
        if (res.code !== 0) throw new Error(res.message || '批次加载失败')
        this.rosterBatch = res.data
      } catch (e) { if (serial === this.rosterSerial) this.rosterError = e.message || '批次加载失败' }
      finally { if (serial === this.rosterSerial) this.rosterLoading = false }
    },
    openRoster(row) {
      this.$router.push({ path: '/admin/orientation/batches', query: { batchId: String(row.id), panel: 'students' } })
    },
    async init() {
      const serial = ++this.requestSerial
      this.ctx = null; this.loading = true; this.error = ''
      try {
        const ctx = await api.getOrientationContext()
        if (serial !== this.requestSerial) return
        if (ctx.code !== 0) throw new Error(ctx.message || '迎新权限读取失败')
        this.ctx = ctx.data
        if (this.noPermission) { this.loading = false; return }
        await this.load()
      } catch (e) { if (serial === this.requestSerial) { this.error = e.message || '迎新权限读取失败'; this.loading = false } }
    },
    async load() {
      const serial = ++this.requestSerial
      const id = this.settingsBatchId
      this.loading = true
      this.error = ''
      this.rows = []; this.total = 0
      if (id) this.page = 1
      try {
        const res = id ? await api.getOrientationBatch(id) : await api.getOrientationBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (serial !== this.requestSerial) return
        if (res.code === 0) {
          this.rows = id ? [res.data] : res.data.list
          this.total = id ? 1 : res.data.total
        } else this.error = res.message
      } catch (e) {
        if (serial === this.requestSerial) this.error = e.message || '加载失败'
      } finally {
        if (serial === this.requestSerial) this.loading = false
      }
    },
    search() {
      this.page = 1
      return this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      return this.load()
    },
    turnPage(p) {
      this.page = p
      return this.load()
    },
    showAllBatches() { return this.$router.push({ path: '/admin/orientation/batches', query: { batchId: '' } }) },
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
      if (this.submitting) return
      const serial = this.actionSerial
      const editing = this.editing
      this.submitting = true
      try {
        const res = editing
          ? await api.updateOrientationBatch(editing.id, form)
          : await api.createOrientationBatch(form)
        if (serial !== this.actionSerial) return
        if (res.code === 0) {
          toast.success(editing ? '已保存' : '已新建批次')
          this.editVisible = false
          if (!editing && res.data?.id) this.openRoster(res.data)
          else await this.load()
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        if (serial === this.actionSerial) this.submitting = false
      }
    },
    closeReason(row) {
      if (row.status !== 'ACTIVE') return '仅进行中的批次可结束'
      if (!this.ctx) return '请先读取当前迎新办理权限'
      if (!['TENANT', 'TENANT_ALL', 'SCHOOL'].includes(this.ctx.dataScope?.scope)) return '结束整批迎新需由具有全校数据范围的迎新管理人员办理'
      if (this.ctx.readonlyTenant) return this.ctx.readonlyReason || '当前学校处于只读状态，暂不能结束批次'
      if (!this.perms['orientation.student.edit']?.allowed) return '当前身份没有结束批次的迎新管理权限'
      return ''
    },
    rowActions(row) {
      return [
        { key: 'students', label: row.status === 'CLOSED' ? '查看新生名单' : '设置新生' },
        ...(row.status === 'CLOSED' ? [{ key: 'archive', label: '继续归档' }] : []),
        { key: 'edit', label: '编辑', disabled: row.status === 'CLOSED', disabledReason: row.status === 'CLOSED' ? '已结束批次不可编辑' : '' },
        { key: 'numbers', label: '一键生成学号', disabled: row.status === 'CLOSED', disabledReason: row.status === 'CLOSED' ? '已结束批次不可再编号' : '' },
        { key: 'refreshFlow', label: '采用最新流程', disabled: row.status !== 'ACTIVE', disabledReason: row.status === 'DRAFT' ? '草稿批次启用时会自动采用最新流程' : row.status === 'CLOSED' ? '已结束批次保持原冻结流程' : '' },
        { key: 'activate', label: '启用', disabled: row.status !== 'DRAFT', disabledReason: row.status !== 'DRAFT' ? '仅草稿可启用' : '' },
        { key: 'close', label: '结束', disabled: !!this.closeReason(row), disabledReason: this.closeReason(row) },
        { key: 'void', label: '作废', disabled: row.status === 'ACTIVE', disabledReason: row.status === 'ACTIVE' ? '进行中批次不可作废' : '' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'students') return this.openRoster(row)
      if (key === 'archive') return this.$router.push({ path: '/admin/orientation/archive', query: { batchId: String(row.id) } })
      if (key === 'close' && this.closeReason(row)) return toast.error(this.closeReason(row))
      if (key === 'edit') return this.openEdit(row)
      if (key === 'numbers') {
        this.numberingRow = row
        this.numberingForm = { prefix: `${row.year || ''}YX`, startNumber: 1, width: 4 }
        this.numberingVisible = true
        return
      }
      this.confirmMode = key
      this.confirmRow = row
      this.confirmVisible = true
    },
    async onConfirm({ reason = '' } = {}) {
      const row = this.confirmRow
      if (!row || this.confirmSubmitting) return
      if (this.confirmMode === 'close' && this.closeReason(row)) return toast.error(this.closeReason(row))
      const serial = this.actionSerial
      const mode = this.confirmMode
      this.confirmSubmitting = true
      try {
        let res
        if (mode === 'activate') res = await api.activateOrientationBatch(row.id)
        else if (mode === 'refreshFlow') res = await api.refreshOrientationBatchFlow(row.id, row.version)
        else if (mode === 'close') res = await api.closeOrientationBatch(row.id)
        else if (mode === 'void') res = await api.voidOrientationBatch(row.id, reason)
        if (serial !== this.actionSerial) return
        if (res && res.code === 0) {
          toast.success(mode === 'close' ? '批次已结束，可继续归档' : '操作成功')
          this.confirmVisible = false
          await this.load()
        } else {
          toast.error((res && res.message) || '操作失败')
        }
      } catch (e) { if (serial === this.actionSerial) toast.error(e.message || '操作未完成，请重试') }
      finally { if (serial === this.actionSerial) this.confirmSubmitting = false }
    },
    async onNumberingConfirm() {
      if (!this.numberingRow || this.numberingSubmitting) return
      const serial = this.actionSerial
      this.numberingSubmitting = true
      try {
        const res = await api.assignOrientationBatchStudentNumbers(this.numberingRow.id, {
          prefix: this.numberingForm.prefix.trim(),
          startNumber: Number(this.numberingForm.startNumber || 1),
          width: Number(this.numberingForm.width || 4)
        })
        if (serial !== this.actionSerial) return
        if (res?.code === 0) {
          toast.success(`已为 ${res.data.assignedCount} 名新生生成学号`)
          this.numberingVisible = false
          await this.load()
        } else toast.error(res?.message || '批量生成失败')
      } finally {
        if (serial === this.actionSerial) this.numberingSubmitting = false
      }
    }
  }
}
</script>

<style scoped>
.ob-roster-header { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 16px 24px 0; color: var(--text-secondary); font-size: 13px; }
.ob-roster-header button { min-height: 40px; padding: 8px 14px; border: 1px solid var(--border-light); border-radius: 6px; background: var(--bg-card); color: var(--primary-600); cursor: pointer; }
.ob-numbering-grid { display: grid; gap: 12px; margin-top: 14px; }
.ob-numbering-grid label { display: grid; gap: 6px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.ob-numbering-note { display: block; margin-top: 12px; color: var(--text-tertiary); }
.ob-current-batch { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: var(--text-secondary); padding: 12px 0; }
.ob-current-batch button { border: 0; background: transparent; color: var(--primary-600); padding: 6px 0; cursor: pointer; }
</style>
