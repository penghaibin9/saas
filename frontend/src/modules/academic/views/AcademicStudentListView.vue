<template>
  <ModulePageShell
    title="学业学生"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的学业学生" description="可调整筛选条件，或确认当前角色的数据范围是否覆盖目标班级" />
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
        <template #cell-gpa="{ row }">
          <span :class="{ 'asl-bad': row.gpa < 2 }">{{ row.gpa.toFixed(1) }}</span>
        </template>
        <template #cell-failedCount="{ row }">
          <StatusTag v-if="row.failedCount" type="danger" :label="row.failedCount + ' 门'" />
          <span v-else class="mp-note">0</span>
        </template>
        <template #cell-credit="{ row }">
          <div class="mp-cell-main">{{ row.obtainedCredits }} / {{ row.requiredCredits }}</div>
          <div class="mp-cell-sub">中期应达 60</div>
        </template>
        <template #cell-makeupRetake="{ row }">
          <span v-if="row.makeupCount || row.retakeCount">补 {{ row.makeupCount }} · 重 {{ row.retakeCount }}</span>
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-warning="{ row }">
          <RiskTag v-if="row.warningLevel !== 'NONE'" :level="row.warningLevel" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.academicStatus === 'NORMAL' ? 'success' : row.academicStatus === 'HELPING' ? 'processing' : 'warning'" :label="statusLabel(row.academicStatus)" dot />
        </template>
        <template #cell-phone="{ row }">{{ row.phone || '未登记' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/academic/students/' + row.id)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.record.edit') }" :title="reason('academic.record.edit')" @click="openEdit(row)">编辑</button>
          <button
            v-if="visible('academic.record.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link asl-danger"
            :class="{ 'is-disabled': !can('academic.record.void') }"
            :title="reason('academic.record.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">列表默认只展示有效记录；作废记录可通过「记录状态」筛选查看。新增/编辑/作废/导入/导出/批量操作均写入审计日志。</p>
    </div>

    <FormDrawer
      v-model:visible="form.visible"
      v-model="form.model"
      :title="form.mode === 'create' ? '新增学业记录' : '编辑学业信息（' + form.model.name + '）'"
      :fields="formFields"
      :submitting="form.submitting"
      note="学业记录以学生主档（student_id）为唯一关联；课程/成绩明细请在「课程成绩」页维护。"
      @submit="submitForm"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废学业记录"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.name : '') + '」的学业记录？作废为逻辑删除，记录保留并可追溯，不可物理删除。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如重复建档、学籍异动等），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ImportDrawer v-model:visible="importVisible" :template="importTemplate" :validate-fn="importValidateFn" :confirm-fn="importConfirmFn" @done="load" />
    <ExportDrawer
      v-model:visible="exportVisible"
      :options="exportOpts"
      :selected-count="selected.length"
      :data-scope-name="ctx.dataScope.name"
      :export-fn="exportFn"
    />
    <ColumnSettingsDrawer v-model:visible="columnVisible" :columns="allColumns" v-model:visible-keys="visibleKeys" />

    <AppDrawer v-model:visible="auditVisible" title="操作留痕（学业学生台账）">
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
 * 学业学生列表（/admin/academic/students）。
 * 管理能力：新增 / 查看 / 编辑 / 作废（留痕）/ 导入 / 导出（脱敏+水印+审计）/ 批量提醒 / 高级筛选 / 列设置 / 操作留痕。
 * 权限按钮全部由 ctx.permissionActions 控制：不可见不渲染，可见无权限置灰并提示原因。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { ImportDrawer, ExportDrawer, ColumnSettingsDrawer, FormDrawer } from '@/modules/academic/components'
import {
  getAcademicStudents, createAcademicRecord, updateAcademicRecord, voidAcademicRecord, batchRemindStudents,
  getFieldColumns, getBatchActions, getImportTemplate, getExportOptions, validateImport, confirmImport, createExport, getAuditLogs
} from '@/modules/academic/api/academic.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', warningLevel: '', academicStatus: '', recordStatus: '' })

export default {
  name: 'AcademicStudentListView',
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
        { key: 'warningLevel', label: '预警等级', type: 'select', options: o.warningLevel },
        { key: 'academicStatus', label: '学业状态', type: 'select', options: o.academicStatus },
        { key: 'recordStatus', label: '记录状态', type: 'select', options: o.recordStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'academic.record.create', label: '＋ 新增学业记录', variant: 'primary' },
        { key: 'import', permission: 'academic.record.import', label: '批量导入' },
        { key: 'export', permission: 'academic.record.export', label: '批量导出' },
        { key: 'columns', permission: 'academic.columns.setting', label: '列设置', variant: 'ghost' },
        { key: 'audit', permission: 'academic.audit.view', label: '操作留痕', variant: 'ghost' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    displayColumns() {
      return this.allColumns.filter((c) => this.visibleKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    formFields() {
      const f = this.ctx.filterOptions
      const base = [
        { key: 'name', label: '姓名', type: 'text', required: true },
        { key: 'studentNo', label: '学号', type: 'text', required: true, placeholder: '如 2023010101' },
        { key: 'classId', label: '班级', type: 'select', required: true, options: f.classes },
        { key: 'requiredCredits', label: '应修学分', type: 'number', required: true },
        { key: 'obtainedCredits', label: '已获学分', type: 'number' }
      ]
      if (this.form.mode === 'edit') {
        return [
          { key: 'requiredCredits', label: '应修学分', type: 'number', required: true },
          { key: 'obtainedCredits', label: '已获学分', type: 'number', required: true },
          { key: 'counselor', label: '辅导员', type: 'text' },
          { key: 'academicStatus', label: '学业状态', type: 'select', options: this.ctx.statusOptions.academicStatus, required: true }
        ]
      }
      return base
    }
  },
  async created() {
    const [cols, batch] = await Promise.all([getFieldColumns('studentList'), getBatchActions('studentList')])
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
    statusLabel(v) {
      return (this.ctx.statusOptions.academicStatus.find((o) => o.value === v) || {}).label || v
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
      const res = await getAcademicStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
        this.form = { visible: true, mode: 'create', submitting: false, model: { requiredCredits: 120 } }
      } else if (key === 'import') {
        if (!this.importTemplate) {
          const res = await getImportTemplate('studentList')
          if (res.code === 0) this.importTemplate = res.data
        }
        this.importVisible = true
      } else if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('studentList')
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
        const res = await batchRemindStudents(this.selected, '学业进度与补考安排')
        if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生发送提醒（站内信 + 小程序），已留痕`)
        else toast.error(res.message)
        this.selected = []
      } else if (key === 'batchExport') {
        if (!this.exportOpts) {
          const res = await getExportOptions('studentList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    openEdit(row) {
      if (!this.can('academic.record.edit')) return
      this.form = {
        visible: true,
        mode: 'edit',
        submitting: false,
        model: {
          id: row.id,
          name: row.name,
          requiredCredits: row.requiredCredits,
          obtainedCredits: row.obtainedCredits,
          counselor: row.counselor,
          academicStatus: row.academicStatus
        }
      }
    },
    async submitForm() {
      this.form.submitting = true
      const m = this.form.model
      const res =
        this.form.mode === 'create'
          ? await createAcademicRecord({ ...m, requiredCredits: Number(m.requiredCredits), obtainedCredits: Number(m.obtainedCredits || 0) })
          : await updateAcademicRecord(m.id, {
              requiredCredits: Number(m.requiredCredits),
              obtainedCredits: Number(m.obtainedCredits),
              counselor: m.counselor,
              academicStatus: m.academicStatus
            })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success(this.form.mode === 'create' ? '学业记录已新增，已写入审计日志' : '学业信息已更新，变更已留痕')
        this.form.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openVoid(row) {
      if (!this.can('academic.record.void')) return
      this.voidDialog = { visible: true, submitting: false, row }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidAcademicRecord(this.voidDialog.row.id, { reason })
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
      return validateImport('studentList', fileName)
    },
    importConfirmFn(payload) {
      return confirmImport('studentList', payload)
    },
    exportFn(payload) {
      return createExport('studentList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.asl-bad {
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
}
.asl-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
