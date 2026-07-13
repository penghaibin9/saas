<template>
  <ModulePageShell
    title="补考重修"
    :subtitle="'补考 ' + makeupTotal + ' 条 · 重修 ' + retakeTotal + ' 条'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'makeup' }" @click="switchTab('makeup')">补考管理</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'retake' }" @click="switchTab('retake')">重修管理</button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="'没有符合条件的' + (tab === 'makeup' ? '补考' : '重修') + '记录'" description="可调整筛选条件后重新查询" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.makeup.batchRemind') }" :title="reason('academic.makeup.batchRemind')" @click="batchRemind">批量提醒</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.makeup.export') }" :title="reason('academic.makeup.export')" @click="openExport">导出选中名单</button>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">
            {{ row.name }}
            <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" />
          </div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-originScore="{ row }">
          <span class="amr-bad">{{ row.originScore }} 分</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-remindCount="{ row }">{{ row.remindCount != null ? row.remindCount + ' 次' : '—' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/academic/students/' + row.studentId)">学生360</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.makeup.edit') }" :title="reason('academic.makeup.edit')" @click="openStatus(row)">更新状态</button>
          <button
            v-if="tab === 'makeup' && visible('academic.record.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link amr-danger"
            :class="{ 'is-disabled': !can('academic.record.void') }"
            :title="reason('academic.record.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">补考未通过将按学校规定自动生成重修建议与学业预警（ACAD-R04）；批量提醒 / 状态更新 / 作废 / 导出均写入审计日志。</p>
    </div>

    <FormDrawer
      v-model:visible="createForm.visible"
      v-model="createForm.model"
      title="新增补考记录"
      :fields="createFields"
      :submitting="createForm.submitting"
      note="补考名单通常由成绩导入自动识别生成，此处用于个别补录。"
      @submit="submitCreate"
    />

    <FormDrawer
      v-model:visible="statusForm.visible"
      v-model="statusForm.model"
      :title="'更新状态（' + statusForm.name + '）'"
      :fields="statusFields"
      :submitting="statusForm.submitting"
      submit-text="更新状态"
      @submit="submitStatus"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废补考记录"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.name + ' · ' + voidDialog.row.courseName : '') + '」补考记录？作废为逻辑删除并留痕。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 补考 / 重修管理（/admin/academic/makeup-retake）。
 * 闭环：名单 → 批量提醒（留痕）→ 状态更新（留痕）→ 导出（脱敏+水印+审计）；补考支持新增与作废。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { ExportDrawer, FormDrawer } from '@/modules/academicAffairs/components'
import {
  getMakeupExamRecords, getRetakeRecords, createMakeupRecord, updateMakeupStatus, updateRetakeStatus, voidMakeupRecord,
  batchRemindMakeup, getFieldColumns, getExportOptions, createExport, getAcademicStudents
} from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'AcademicMakeupRetakeView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, ExportDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'makeup',
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      makeupTotal: 0,
      retakeTotal: 0,
      makeupColumns: [],
      studentsOptions: [],
      createForm: { visible: false, submitting: false, model: {} },
      statusForm: { visible: false, submitting: false, name: '', model: {}, row: null },
      voidDialog: { visible: false, submitting: false, row: null },
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 课程' },
        { key: 'status', label: '状态', type: 'select', options: this.tab === 'makeup' ? o.makeupStatus : o.retakeStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = [
        { key: 'create', permission: 'academic.makeup.create', label: '＋ 新增补考记录', variant: 'primary', onlyMakeup: true },
        { key: 'export', permission: 'academic.makeup.export', label: '导出名单' }
      ].filter((a) => !a.onlyMakeup || this.tab === 'makeup')
      return list
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    columns() {
      if (this.tab === 'makeup') {
        return this.makeupColumns.length
          ? this.makeupColumns
          : [
              { key: 'name', title: '学生' },
              { key: 'courseName', title: '课程' },
              { key: 'term', title: '学期' },
              { key: 'originScore', title: '原成绩' },
              { key: 'examDate', title: '考核安排' },
              { key: 'status', title: '状态' },
              { key: 'remindCount', title: '已提醒' },
              { key: 'actions', title: '操作', width: '200px' }
            ]
      }
      return [
        { key: 'name', title: '学生' },
        { key: 'courseName', title: '课程' },
        { key: 'retakeTerm', title: '重修学期' },
        { key: 'reason', title: '重修原因' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    },
    createFields() {
      const f = this.ctx.filterOptions
      return [
        { key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions },
        { key: 'courseId', label: '课程', type: 'select', required: true, options: f.courses },
        { key: 'originScore', label: '原成绩', type: 'number', required: true },
        { key: 'examDate', label: '考核安排', type: 'text', required: true, placeholder: '如 2026-09-06 09:00 · 实训楼A302' }
      ]
    },
    statusFields() {
      const o = this.ctx.statusOptions
      return [{ key: 'status', label: '新状态', type: 'select', required: true, options: this.tab === 'makeup' ? o.makeupStatus : o.retakeStatus }]
    }
  },
  async created() {
    const cols = await getFieldColumns('makeupList')
    if (cols.code === 0) this.makeupColumns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    this.loadTotals()
    this.load()
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
      const o = this.ctx.statusOptions
      return ((this.tab === 'makeup' ? o.makeupStatus : o.retakeStatus).find((x) => x.value === v) || {}).label || v
    },
    statusTone(v) {
      if (['PASSED'].includes(v)) return 'success'
      if (['PENDING_EXAM', 'ENROLLING'].includes(v)) return 'warning'
      if (['FAILED', 'ABSENT'].includes(v)) return 'danger'
      return 'processing'
    },
    switchTab(tab) {
      this.tab = tab
      this.selected = []
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
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
    async loadTotals() {
      const [mk, rt] = await Promise.all([getMakeupExamRecords({ pageSize: 1 }), getRetakeRecords({ pageSize: 1 })])
      if (mk.code === 0) this.makeupTotal = mk.data.total
      if (rt.code === 0) this.retakeTotal = rt.data.total
    },
    async load() {
      this.loading = true
      this.error = ''
      const fn = this.tab === 'makeup' ? getMakeupExamRecords : getRetakeRecords
      const res = await fn({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
        if (!this.studentsOptions.length) {
          const res = await getAcademicStudents({ pageSize: 100 })
          if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
        }
        this.createForm = { visible: true, submitting: false, model: {} }
      } else if (key === 'export') {
        this.openExport()
      }
    },
    async openExport() {
      if (!this.can('academic.makeup.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('makeupList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    async batchRemind() {
      if (!this.can('academic.makeup.batchRemind')) return
      const res = await batchRemindMakeup(this.selected)
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生发送考核提醒（站内信 + 小程序），已留痕`)
      else toast.error(res.message)
      this.selected = []
      this.load()
    },
    async submitCreate() {
      this.createForm.submitting = true
      const res = await createMakeupRecord(this.createForm.model)
      this.createForm.submitting = false
      if (res.code === 0) {
        toast.success('补考记录已新增，已写入审计日志')
        this.createForm.visible = false
        this.loadTotals()
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openStatus(row) {
      if (!this.can('academic.makeup.edit')) return
      this.statusForm = { visible: true, submitting: false, name: row.name + ' · ' + row.courseName, model: { status: row.status }, row }
    },
    async submitStatus() {
      this.statusForm.submitting = true
      const fn = this.tab === 'makeup' ? updateMakeupStatus : updateRetakeStatus
      const res = await fn(this.statusForm.row.id, { status: this.statusForm.model.status })
      this.statusForm.submitting = false
      if (res.code === 0) {
        toast.success('状态已更新，变更已留痕')
        this.statusForm.visible = false
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
      const res = await voidMakeupRecord(this.voidDialog.row.id, { reason })
      this.voidDialog.submitting = false
      if (res.code === 0) {
        toast.success('补考记录已作废（逻辑删除），原因已留痕')
        this.voidDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    exportFn(payload) {
      return createExport('makeupList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.amr-bad {
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
}
.amr-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
