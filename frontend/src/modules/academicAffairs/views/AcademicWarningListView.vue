<template>
  <ModulePageShell
    title="学业预警"
    :subtitle="'共 ' + pagination.total + ' 条 · 预警由规则引擎自动生成或人工上报'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的学业预警" description="可调整筛选条件；预警由成绩/学分规则自动触发，也可人工上报" />
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
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.warning.batchRemind') }" :title="reason('academic.warning.batchRemind')" @click="batchRemind">批量提醒</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.warning.batchAssign') }" :title="reason('academic.warning.batchAssign')" @click="openAssign">批量分配跟进人</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.warning.export') }" :title="reason('academic.warning.export')" @click="openExport">导出选中</button>
        </template>
        <template #cell-code="{ row }">
          <div class="mp-cell-main">
            {{ row.code }}
            <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" />
          </div>
          <div class="mp-cell-sub">{{ row.sourceRule }}</div>
        </template>
        <template #cell-type="{ row }">{{ typeLabel(row.type) }}</template>
        <template #cell-level="{ row }">
          <RiskTag :level="row.level" />
        </template>
        <template #cell-owner="{ row }">{{ row.owner || '未分配' }}</template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/academic/warnings/' + row.id)">跟进详情</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('academic.warning.editLevel') }" :title="reason('academic.warning.editLevel')" @click="openLevel(row)">调等级</button>
          <button
            v-if="visible('academic.warning.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link awl-danger"
            :class="{ 'is-disabled': !can('academic.warning.void') }"
            :title="reason('academic.warning.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">作废用于误报处理（逻辑删除，原因必填留痕）；关闭/升级请进入跟进详情操作。导出名单默认脱敏并含水印，导出行为写入审计日志。</p>
    </div>

    <FormDrawer
      v-model:visible="createForm.visible"
      v-model="createForm.model"
      title="新增学业预警（人工上报）"
      :fields="createFields"
      :submitting="createForm.submitting"
      note="规则引擎（ACAD-R 系列）会自动生成大部分预警；人工上报用于教师/辅导员主动发现的学业风险。"
      @submit="submitCreate"
    />

    <FormDrawer
      v-model:visible="levelForm.visible"
      v-model="levelForm.model"
      :title="'调整预警等级（' + levelForm.code + '）'"
      :fields="levelFields"
      :submitting="levelForm.submitting"
      submit-text="确认调整"
      @submit="submitLevel"
    />

    <FormDrawer
      v-model:visible="assignForm.visible"
      v-model="assignForm.model"
      :title="'批量分配跟进人（已选 ' + selected.length + ' 条）'"
      :fields="assignFields"
      :submitting="assignForm.submitting"
      submit-text="确认分配"
      @submit="submitAssign"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废预警（误报）"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.code : '') + '」？作废为逻辑删除，预警与处理过程保留可追溯。'"
      confirm-text="确认作废"
      require-reason
      reason-label="误报说明"
      reason-placeholder="请说明误报原因（如数据同步错误、规则误命中），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
    <ColumnSettingsDrawer v-model:visible="columnVisible" :columns="allColumns" v-model:visible-keys="visibleKeys" />
  </ModulePageShell>
</template>

<script>
/**
 * 学业预警学生列表（/admin/academic/warnings）。
 * 管理能力：新增预警 / 跟进详情 / 调整等级（原因留痕）/ 作废（误报留痕）/ 批量提醒 / 批量分配跟进人 / 导出（脱敏+水印）/ 列设置。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { ExportDrawer, ColumnSettingsDrawer, FormDrawer } from '@/modules/academicAffairs/components'
import {
  getAcademicWarnings, createWarning, updateWarningLevel, voidWarning, assignWarnings, remindWarnings,
  getFieldColumns, getExportOptions, createExport, getAcademicStudents
} from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', level: '', status: '', classId: '', recordStatus: '' })

export default {
  name: 'AcademicWarningListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, ExportDrawer, ColumnSettingsDrawer, FormDrawer
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
      studentsOptions: [],
      createForm: { visible: false, submitting: false, model: {} },
      levelForm: { visible: false, submitting: false, code: '', model: {}, row: null },
      assignForm: { visible: false, submitting: false, model: {} },
      voidDialog: { visible: false, submitting: false, row: null },
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
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 预警编号 / 原因' },
        { key: 'type', label: '预警类型', type: 'select', options: o.warningType },
        { key: 'level', label: '风险等级', type: 'select', options: o.warningLevel },
        { key: 'status', label: '处理状态', type: 'select', options: o.warningStatus },
        { key: 'classId', label: '班级', type: 'select', options: f.classes },
        { key: 'recordStatus', label: '记录状态', type: 'select', options: o.recordStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'academic.warning.create', label: '＋ 新增预警', variant: 'primary' },
        { key: 'export', permission: 'academic.warning.export', label: '导出预警名单' },
        { key: 'columns', permission: 'academic.columns.setting', label: '列设置', variant: 'ghost' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    displayColumns() {
      return this.allColumns.filter((c) => this.visibleKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    createFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions },
        { key: 'type', label: '预警类型', type: 'select', required: true, options: o.warningType },
        { key: 'level', label: '风险等级', type: 'select', required: true, options: o.warningLevel },
        { key: 'reason', label: '触发原因', type: 'textarea', required: true, placeholder: '请描述学业风险表现（不少于 5 个字）' },
        { key: 'deadline', label: '处理期限', type: 'date' }
      ]
    },
    levelFields() {
      return [
        { key: 'level', label: '新等级', type: 'select', required: true, options: this.ctx.statusOptions.warningLevel },
        { key: 'reason', label: '调整原因', type: 'textarea', required: true, placeholder: '请说明等级调整依据（不少于 5 个字）' }
      ]
    },
    assignFields() {
      return [{ key: 'ownerId', label: '跟进人', type: 'select', required: true, options: this.ctx.filterOptions.owners }]
    }
  },
  async created() {
    const cols = await getFieldColumns('warningList')
    if (cols.code === 0) {
      this.allColumns = cols.data
      this.visibleKeys = cols.data.filter((c) => c.locked || c.default).map((c) => c.key)
    }
    await this.load()
    if (this.$route.query.create) this.openCreate(String(this.$route.query.create))
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
    typeLabel(v) {
      return (this.ctx.statusOptions.warningType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.warningStatus.find((o) => o.value === v) || {}).label || v
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
      const res = await getAcademicWarnings({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'create') this.openCreate()
      else if (key === 'export') this.openExport()
      else if (key === 'columns') this.columnVisible = true
    },
    async openCreate(studentId = '') {
      if (!this.can('academic.warning.create')) return
      if (!this.studentsOptions.length) {
        const res = await getAcademicStudents({ pageSize: 100 })
        if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
      }
      this.createForm = { visible: true, submitting: false, model: { studentId, level: 'MEDIUM' } }
    },
    async submitCreate() {
      this.createForm.submitting = true
      const res = await createWarning(this.createForm.model)
      this.createForm.submitting = false
      if (res.code === 0) {
        toast.success(`预警 ${res.data.code} 已创建，已写入审计日志`)
        this.createForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openLevel(row) {
      if (!this.can('academic.warning.editLevel')) return
      this.levelForm = { visible: true, submitting: false, code: row.code, model: { level: row.level, reason: '' }, row }
    },
    async submitLevel() {
      this.levelForm.submitting = true
      const res = await updateWarningLevel(this.levelForm.row.id, this.levelForm.model)
      this.levelForm.submitting = false
      if (res.code === 0) {
        toast.success('预警等级已调整，原因已留痕')
        this.levelForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openAssign() {
      if (!this.can('academic.warning.batchAssign')) return
      this.assignForm = { visible: true, submitting: false, model: {} }
    },
    async submitAssign() {
      this.assignForm.submitting = true
      const owner = this.ctx.filterOptions.owners.find((o) => o.value === this.assignForm.model.ownerId)
      const res = await assignWarnings(this.selected, { ownerId: this.assignForm.model.ownerId, ownerName: owner ? owner.label : '' })
      this.assignForm.submitting = false
      if (res.code === 0) {
        toast.success(`已将 ${res.data.count} 条预警分配给 ${owner.label}，已留痕`)
        this.assignForm.visible = false
        this.selected = []
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async batchRemind() {
      if (!this.can('academic.warning.batchRemind')) return
      const res = await remindWarnings(this.selected)
      if (res.code === 0) toast.success(`已向 ${res.data.count} 条预警的学生与跟进人发送提醒，已留痕`)
      else toast.error(res.message)
      this.selected = []
      this.load()
    },
    openVoid(row) {
      if (!this.can('academic.warning.void')) return
      this.voidDialog = { visible: true, submitting: false, row }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidWarning(this.voidDialog.row.id, { reason })
      this.voidDialog.submitting = false
      if (res.code === 0) {
        toast.success('预警已作废（误报，逻辑删除），说明已留痕')
        this.voidDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openExport() {
      if (!this.can('academic.warning.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('warningList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('warningList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.awl-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
