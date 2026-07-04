<template>
  <ModulePageShell
    title="学生服务"
    :subtitle="'共 ' + pagination.total + ' 人 · 手机号/学号默认脱敏展示'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的学生" description="可调整筛选条件，或确认当前角色的数据范围是否覆盖目标班级/楼栋" />
      <DataTable
        v-else
        :columns="displayColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button
            v-for="b in batchActionList"
            :key="b.key"
            class="mp-link"
            :class="{ 'is-disabled': !can(b.permission) }"
            :title="reason(b.permission)"
            @click="onBatch(b.key, b.permission)"
          >
            {{ b.label }}
          </button>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">
            {{ row.name }}
            <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" />
          </div>
          <div class="mp-cell-sub">{{ maskNo(row.studentNo) }}</div>
        </template>
        <template #cell-dorm="{ row }">
          <div class="mp-cell-main">{{ row.building }}</div>
          <div class="mp-cell-sub">{{ row.room }}</div>
        </template>
        <template #cell-leaveSummary="{ row }">
          <span v-if="row.pendingLeave"><StatusTag type="warning" :label="'待批 ' + row.pendingLeave" dot /></span>
          <span v-else-if="row.leaveCount">{{ row.leaveCount }} 次</span>
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-grantSummary="{ row }">
          <span :class="{ 'mp-note': row.grantSummary === '无申请' }">{{ row.grantSummary }}</span>
        </template>
        <template #cell-disciplineSummary="{ row }">
          <StatusTag v-if="row.disciplineCount" type="danger" :label="row.disciplineCount + ' 条'" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-workOrderSummary="{ row }">
          <span v-if="row.workOrderCount">{{ row.workOrderCount }} 单</span>
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-careLevel="{ row }">
          <StatusTag
            :type="row.careLevel === 'NORMAL' ? 'default' : row.careLevel === 'FOCUS' ? 'warning' : 'danger'"
            :label="careLabel(row.careLevel)"
            dot
          />
        </template>
        <template #cell-risk="{ row }">
          <RiskTag v-if="row.riskLevel !== 'LOW'" :level="row.riskLevel" />
          <span v-else class="mp-note">低</span>
        </template>
        <template #cell-phone="{ row }">{{ row.phone || '未登记' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + row.id)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.record.edit') }" :title="reason('campus.record.edit')" @click="openEdit(row)">编辑</button>
          <button
            v-if="visible('campus.record.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link ssl-danger"
            :class="{ 'is-disabled': !can('campus.record.void') }"
            :title="reason('campus.record.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">新增/编辑/作废/导入/导出/批量操作均写入审计日志；心理与困难帮扶敏感信息不在本列表展示，详情页按角色收敛。</p>
    </div>

    <FormDrawer
      v-model:visible="form.visible"
      v-model="form.model"
      :title="form.mode === 'create' ? '新增服务记录' : '编辑服务信息（' + form.model.name + '）'"
      :fields="formFields"
      :submitting="form.submitting"
      note="服务记录以学生主档（student_id）为唯一关联；请假/资助/工单等明细在对应页面办理。"
      @submit="submitForm"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废服务记录"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.name : '') + '」的服务记录？作废为逻辑删除，记录保留并可追溯。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如重复建档、学籍异动等），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ImportDrawer v-model:visible="importVisible" :template="importTemplate" :validate-fn="importValidateFn" :confirm-fn="importConfirmFn" @done="load" />
    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
    <ColumnSettingsDrawer v-model:visible="columnVisible" :columns="allColumns" v-model:visible-keys="visibleKeys" />

    <AppDrawer v-model:visible="auditVisible" title="操作留痕（在校服务）">
      <table class="mp-audit">
        <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>明细</th></tr></thead>
        <tbody>
          <tr v-for="a in auditRows" :key="a.id">
            <td>{{ a.time }}</td>
            <td class="is-who">{{ a.operator }}<div class="mp-cell-sub">{{ a.roleName }}</div></td>
            <td>{{ a.action }}</td>
            <td>{{ a.detail }}</td>
          </tr>
        </tbody>
      </table>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 在校学生服务列表（/admin/campus-service/students）。
 * 管理能力：新增 / 查看 / 编辑 / 作废（留痕）/ 导入 / 导出（脱敏+水印+审计）/ 批量提醒 / 高级筛选 / 列设置 / 操作留痕。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { ImportDrawer, ExportDrawer, ColumnSettingsDrawer, FormDrawer } from '@/modules/campusService/components'
import {
  getServiceStudents, createServiceRecord, updateServiceRecord, voidServiceRecord, batchRemindServiceStudents,
  getFieldColumns, getBatchActions, getImportTemplate, getExportOptions, validateImport, confirmImport, createExport, getAuditLogs
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', careLevel: '', riskLevel: '', recordStatus: '' })

export default {
  name: 'ServiceStudentListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppDrawer, ImportDrawer, ExportDrawer, ColumnSettingsDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      allColumns: [],
      visibleKeys: [],
      batchActionList: [],
      form: { visible: false, mode: 'create', submitting: false, model: {} },
      voidDialog: { visible: false, submitting: false, row: null },
      importVisible: false,
      importTemplate: null,
      exportVisible: false,
      exportOpts: null,
      columnVisible: false,
      auditVisible: false,
      auditRows: []
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号' },
        { key: 'classId', label: '班级', type: 'select', options: f.classes },
        { key: 'careLevel', label: '关怀级别', type: 'select', options: o.careLevel },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: o.riskLevel },
        { key: 'recordStatus', label: '记录状态', type: 'select', options: o.recordStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'campus.record.create', label: '＋ 新增服务记录', variant: 'primary' },
        { key: 'import', permission: 'campus.record.import', label: '批量导入' },
        { key: 'export', permission: 'campus.record.export', label: '批量导出' },
        { key: 'columns', permission: 'campus.columns.setting', label: '列设置', variant: 'ghost' },
        { key: 'audit', permission: 'campus.audit.view', label: '操作留痕', variant: 'ghost' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    displayColumns() {
      return this.allColumns.filter((c) => this.visibleKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    formFields() {
      const f = this.ctx.filterOptions
      const o = this.ctx.statusOptions
      if (this.form.mode === 'edit') {
        return [
          { key: 'buildingId', label: '宿舍楼栋', type: 'select', options: f.buildings, required: true },
          { key: 'room', label: '房间-床位', type: 'text', required: true, placeholder: '如 312-2' },
          { key: 'counselor', label: '辅导员', type: 'text' },
          { key: 'careLevel', label: '关怀级别', type: 'select', options: o.careLevel, required: true }
        ]
      }
      return [
        { key: 'name', label: '姓名', type: 'text', required: true },
        { key: 'studentNo', label: '学号', type: 'text', required: true, placeholder: '如 2023010101' },
        { key: 'classId', label: '班级', type: 'select', required: true, options: f.classes },
        { key: 'room', label: '房间-床位', type: 'text', placeholder: '如 312-2' },
        { key: 'careLevel', label: '关怀级别', type: 'select', options: o.careLevel }
      ]
    }
  },
  async created() {
    const [cols, batch] = await Promise.all([getFieldColumns('serviceList'), getBatchActions('serviceList')])
    if (cols.code === 0) {
      this.allColumns = cols.data
      this.visibleKeys = cols.data.filter((c) => c.locked || c.default).map((c) => c.key)
    }
    if (batch.code === 0) this.batchActionList = batch.data
    this.load()
    if (this.$route.query.tab === 'audit') this.onToolbar('audit')
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    visible(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    careLabel(v) {
      return (this.ctx.statusOptions.careLevel.find((o) => o.value === v) || {}).label || v
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getServiceStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'create') {
        this.form = { visible: true, mode: 'create', submitting: false, model: { careLevel: 'NORMAL' } }
      } else if (key === 'import') {
        if (!this.importTemplate) {
          const res = await getImportTemplate('serviceList')
          if (res.code === 0) this.importTemplate = res.data
        }
        this.importVisible = true
      } else if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('serviceList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      } else if (key === 'columns') {
        this.columnVisible = true
      } else if (key === 'audit') {
        const res = await getAuditLogs({ pageSize: 30 })
        if (res.code === 0) this.auditRows = res.data.list
        this.auditVisible = true
      }
    },
    async onBatch(key, permission) {
      if (!this.can(permission)) return
      if (key === 'batchRemind') {
        const res = await batchRemindServiceStudents(this.selected, '在校服务事项办理')
        if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生发送提醒（站内信 + 小程序），已留痕`)
        else toast.error(res.message)
        this.selected = []
      } else if (key === 'batchExport') {
        if (!this.exportOpts) {
          const res = await getExportOptions('serviceList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    openEdit(row) {
      if (!this.can('campus.record.edit')) return
      this.form = {
        visible: true,
        mode: 'edit',
        submitting: false,
        model: { id: row.id, name: row.name, buildingId: row.buildingId, room: row.room, counselor: row.counselor, careLevel: row.careLevel }
      }
    },
    async submitForm() {
      this.form.submitting = true
      const m = this.form.model
      let res
      if (this.form.mode === 'create') {
        res = await createServiceRecord({ ...m })
      } else {
        const building = this.ctx.filterOptions.buildings.find((b) => b.value === m.buildingId)
        res = await updateServiceRecord(m.id, {
          buildingId: m.buildingId,
          building: building ? building.label : '',
          room: m.room,
          counselor: m.counselor,
          careLevel: m.careLevel
        })
      }
      this.form.submitting = false
      if (res.code === 0) {
        toast.success(this.form.mode === 'create' ? '服务记录已新增，已写入审计日志' : '服务信息已更新，变更已留痕')
        this.form.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openVoid(row) {
      if (!this.can('campus.record.void')) return
      this.voidDialog = { visible: true, submitting: false, row }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidServiceRecord(this.voidDialog.row.id, { reason })
      this.voidDialog.submitting = false
      if (res.code === 0) {
        toast.success('记录已作废（逻辑删除），原因已留痕可追溯')
        this.voidDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    importValidateFn(fileName) {
      return validateImport('serviceList', fileName)
    },
    importConfirmFn(payload) {
      return confirmImport('serviceList', payload)
    },
    exportFn(payload) {
      return createExport('serviceList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ssl-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
