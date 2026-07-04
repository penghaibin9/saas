<template>
  <ModulePageShell
    title="课程成绩"
    :subtitle="'成绩为教务同步/导入摘要 · 共 ' + pagination.total + ' 条'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">课程摘要（本数据范围）</span>
          <span class="mp-note">课程库同步自教务系统，本页不做排课/选课</span>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead><tr><th>课程</th><th>学期</th><th>性质</th><th>学分</th><th>任课教师</th><th>人数</th><th>平均分</th><th>通过率</th></tr></thead>
            <tbody>
              <tr v-for="c in courses" :key="c.id">
                <td class="is-who">{{ c.courseName }}</td>
                <td>{{ c.term }}</td>
                <td>{{ natureLabel(c.nature) }}</td>
                <td>{{ c.credit }}</td>
                <td>{{ c.teacherName }}</td>
                <td>{{ c.studentCount }}</td>
                <td>{{ c.avgScore }}</td>
                <td :class="{ 'agl-bad': c.passRate < 85 }">{{ c.passRate }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的成绩记录" description="可调整筛选条件，或先通过「导入成绩」同步教务数据" />
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
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.grade.export') }" :title="reason('academic.grade.export')" @click="openExport">导出选中成绩</button>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">
            {{ row.name }}
            <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" />
          </div>
        </template>
        <template #cell-nature="{ row }">{{ natureLabel(row.nature) }}</template>
        <template #cell-score="{ row }">
          <span :class="{ 'agl-bad': row.score < 60 }">{{ row.score }}</span>
        </template>
        <template #cell-passStatus="{ row }">
          <StatusTag :type="row.passStatus === 'PASSED' ? 'success' : 'danger'" :label="row.passStatus === 'PASSED' ? '通过' : '未通过'" dot />
        </template>
        <template #cell-examType="{ row }">{{ examTypeLabel(row.examType) }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/academic/students/' + row.studentId)">学生360</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.grade.edit') }" :title="reason('academic.grade.edit')" @click="openEdit(row)">改分</button>
          <button
            v-if="visible('academic.grade.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link agl-danger"
            :class="{ 'is-disabled': !can('academic.grade.void') }"
            :title="reason('academic.grade.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">成绩改分必须填写变更原因并留痕（变更前后分数写入审计日志）；作废为逻辑删除。导入需模板校验，导出默认脱敏并含水印。</p>
    </div>

    <FormDrawer
      v-model:visible="form.visible"
      v-model="form.model"
      :title="form.mode === 'create' ? '新增成绩记录' : '成绩变更（' + form.model.name + ' · ' + form.model.courseName + '）'"
      :fields="formFields"
      :submitting="form.submitting"
      :note="form.mode === 'create' ? '手工录入仅用于少量补录，批量成绩请使用「导入成绩」。' : '成绩变更将记录变更前后分数与原因，全程可追溯。'"
      @submit="submitForm"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废成绩记录"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.name + ' · ' + voidDialog.row.courseName : '') + '」成绩记录？作废为逻辑删除，原始分数保留可追溯。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如录入错误、批次重复），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ImportDrawer v-model:visible="importVisible" :template="importTemplate" :validate-fn="importValidateFn" :confirm-fn="importConfirmFn" @done="load" />
    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
    <ColumnSettingsDrawer v-model:visible="columnVisible" :columns="allColumns" v-model:visible-keys="visibleKeys" />
  </ModulePageShell>
</template>

<script>
/**
 * 课程成绩管理（/admin/academic/grades）。
 * 闭环：课程摘要 → 成绩记录 → 新增/改分（原因必填留痕）/ 作废 / 批量导入（校验+回执）/ 导出（脱敏+水印+审计）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { ImportDrawer, ExportDrawer, ColumnSettingsDrawer, FormDrawer } from '@/modules/academic/components'
import {
  getCourseRecords, getGradeRecords, createGradeRecord, updateGradeRecord, voidGradeRecord, getAcademicStudents,
  getFieldColumns, getImportTemplate, getExportOptions, validateImport, confirmImport, createExport
} from '@/modules/academic/api/academic.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', courseId: '', term: '', passStatus: '', examType: '', recordStatus: '' })

export default {
  name: 'AcademicGradeListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, ImportDrawer, ExportDrawer, ColumnSettingsDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      courses: [],
      studentsOptions: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      allColumns: [],
      visibleKeys: [],
      form: { visible: false, mode: 'create', submitting: false, model: {} },
      voidDialog: { visible: false, submitting: false, row: null },
      importVisible: false,
      importTemplate: null,
      exportVisible: false,
      exportOpts: null,
      columnVisible: false
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 课程' },
        { key: 'courseId', label: '课程', type: 'select', options: f.courses },
        { key: 'term', label: '学期', type: 'select', options: o.terms },
        { key: 'passStatus', label: '是否通过', type: 'select', options: o.passStatus.filter((s) => s.value !== 'PENDING') },
        { key: 'examType', label: '考试类型', type: 'select', options: o.examType },
        { key: 'recordStatus', label: '记录状态', type: 'select', options: o.recordStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'academic.grade.create', label: '＋ 新增成绩', variant: 'primary' },
        { key: 'import', permission: 'academic.grade.import', label: '导入成绩' },
        { key: 'export', permission: 'academic.grade.export', label: '导出成绩' },
        { key: 'columns', permission: 'academic.columns.setting', label: '列设置', variant: 'ghost' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    displayColumns() {
      return this.allColumns.filter((c) => this.visibleKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    formFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      if (this.form.mode === 'edit') {
        return [
          { key: 'score', label: '新成绩（0-100）', type: 'number', required: true },
          { key: 'reason', label: '变更原因', type: 'textarea', required: true, placeholder: '请说明改分原因（如成绩复核、录入错误），不少于 5 个字' }
        ]
      }
      return [
        { key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions },
        { key: 'courseId', label: '课程', type: 'select', required: true, options: f.courses },
        { key: 'term', label: '学期', type: 'select', required: true, options: o.terms },
        { key: 'score', label: '成绩（0-100）', type: 'number', required: true },
        { key: 'examType', label: '考试类型', type: 'select', required: true, options: o.examType }
      ]
    }
  },
  async created() {
    const cols = await getFieldColumns('gradeList')
    if (cols.code === 0) {
      this.allColumns = cols.data
      this.visibleKeys = cols.data.filter((c) => c.locked || c.default).map((c) => c.key)
    }
    const cr = await getCourseRecords({ pageSize: 20 })
    if (cr.code === 0) this.courses = cr.data.list
    this.load()
    if (this.$route.query.import === '1') this.onToolbar('import')
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
    natureLabel(v) {
      return (this.ctx.statusOptions.courseNature.find((o) => o.value === v) || {}).label || v
    },
    examTypeLabel(v) {
      return (this.ctx.statusOptions.examType.find((o) => o.value === v) || {}).label || v
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
      const res = await getGradeRecords({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
        this.form = { visible: true, mode: 'create', submitting: false, model: { examType: 'FINAL', term: this.ctx.statusOptions.terms[0].value } }
      } else if (key === 'import') {
        if (!this.importTemplate) {
          const res = await getImportTemplate('gradeList')
          if (res.code === 0) this.importTemplate = res.data
        }
        this.importVisible = true
      } else if (key === 'export') {
        this.openExport()
      } else if (key === 'columns') {
        this.columnVisible = true
      }
    },
    async openExport() {
      if (!this.exportOpts) {
        const res = await getExportOptions('gradeList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    openEdit(row) {
      if (!this.can('academic.grade.edit')) return
      this.form = { visible: true, mode: 'edit', submitting: false, model: { id: row.id, name: row.name, courseName: row.courseName, score: row.score, reason: '' } }
    },
    async submitForm() {
      this.form.submitting = true
      const m = this.form.model
      const res =
        this.form.mode === 'create'
          ? await createGradeRecord({ studentId: m.studentId, courseId: m.courseId, term: m.term, score: m.score, examType: m.examType })
          : await updateGradeRecord(m.id, { score: m.score, reason: m.reason })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success(this.form.mode === 'create' ? '成绩已录入，已写入审计日志' : '成绩已变更，变更前后分数已留痕')
        this.form.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openVoid(row) {
      if (!this.can('academic.grade.void')) return
      this.voidDialog = { visible: true, submitting: false, row }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidGradeRecord(this.voidDialog.row.id, { reason })
      this.voidDialog.submitting = false
      if (res.code === 0) {
        toast.success('成绩记录已作废（逻辑删除），原因已留痕')
        this.voidDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    importValidateFn(fileName) {
      return validateImport('gradeList', fileName)
    },
    importConfirmFn(payload) {
      return confirmImport('gradeList', payload)
    },
    exportFn(payload) {
      return createExport('gradeList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.agl-bad {
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
}
.agl-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
