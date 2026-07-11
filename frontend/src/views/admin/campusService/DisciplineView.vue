<template>
  <ModulePageShell
    title="违纪处分"
    :subtitle="'共 ' + pagination.total + ' 条 · 处分记录按流程告知学生并进入学生360'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的处分记录" description="可调整筛选条件；处分记录须依据学校学生管理规定录入" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-code="{ row }">
          <div class="mp-cell-main">
            {{ row.code }}
            <StatusTag v-if="row.recordStatus === 'VOIDED'" type="default" label="已作废" />
          </div>
          <div class="mp-cell-sub">{{ row.docNo }}</div>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-type="{ row }">
          <StatusTag :type="row.type === 'WARNING' ? 'warning' : 'danger'" :label="typeLabel(row.type)" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'EFFECTIVE' ? 'danger' : 'default'" :label="row.status === 'EFFECTIVE' ? '生效中' : '已解除'" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + row.studentId)">学生服务</button>
          <button
            v-if="row.status === 'EFFECTIVE' && row.recordStatus === 'ACTIVE'"
            class="mp-link"
            :class="{ 'is-disabled': !can('campus.discipline.edit') }"
            :title="reason('campus.discipline.edit')"
            @click="openRevoke(row)"
          >
            解除处分
          </button>
          <button
            v-if="visible('campus.discipline.void') && row.recordStatus === 'ACTIVE'"
            class="mp-link dsv-danger"
            :class="{ 'is-disabled': !can('campus.discipline.void') }"
            :title="reason('campus.discipline.void')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        处分的新增/解除/作废均需说明并写入审计日志；作废用于录入错误（逻辑删除），解除用于察看期满按程序解除。导出记录默认脱敏并含水印。
      </p>
    </div>

    <FormDrawer
      v-model:visible="createForm.visible"
      v-model="createForm.model"
      title="新增处分记录"
      :fields="createFields"
      :submitting="createForm.submitting"
      note="录入前请确认已完成告知与申诉程序；记录将进入学生360并同步相关角色。"
      @submit="submitCreate"
    />

    <AppConfirmDialog
      v-model:visible="revokeDialog.visible"
      type="primary"
      title="解除处分"
      :message="'确认解除「' + (revokeDialog.row ? revokeDialog.row.code + ' · ' + revokeDialog.row.name : '') + '」的处分？解除后记录保留，状态置为已解除。'"
      confirm-text="确认解除"
      require-reason
      reason-label="解除说明"
      reason-placeholder="请说明解除依据（如察看期内表现良好，按程序解除），不少于 5 个字"
      :submitting="revokeDialog.submitting"
      @confirm="submitRevoke"
    />

    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废处分记录"
      :message="'确认作废「' + (voidDialog.row ? voidDialog.row.code : '') + '」？作废仅用于录入错误，为逻辑删除并留痕。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如重复录入、信息错误），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="0" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 违纪 / 处分记录管理（/admin/campus-service/discipline）。
 * 管理能力：详情（独立详情页，2026-07-10 第一批交互改造）/ 新增（说明必填）/ 解除（说明留痕）/
 * 作废（逻辑删除留痕）/ 导出（脱敏+水印+审计）/ 高级筛选；筛选与页码同步路由 query，从详情返回不丢上下文。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { ExportDrawer, FormDrawer, readListState, writeListState } from '@/modules/campusService/components'
import {
  getDisciplineRecords, createDisciplineRecord, updateDisciplineRecord, voidDisciplineRecord,
  getFieldColumns, getExportOptions, createExport, getServiceStudents
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'type', 'status', 'recordStatus']
const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '', recordStatus: '' })

export default {
  name: 'DisciplineView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, ExportDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [],
      studentsOptions: [],
      createForm: { visible: false, submitting: false, model: {} },
      revokeDialog: { visible: false, submitting: false, row: null },
      voidDialog: { visible: false, submitting: false, row: null },
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 编号 / 事由' },
        { key: 'type', label: '处分类型', type: 'select', options: o.disciplineType },
        { key: 'status', label: '状态', type: 'select', options: o.disciplineStatus },
        { key: 'recordStatus', label: '记录状态', type: 'select', options: o.recordStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'campus.discipline.create', label: '＋ 新增处分记录', variant: 'primary' },
        { key: 'export', permission: 'campus.discipline.export', label: '导出处分记录' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    createFields() {
      return [
        { key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions },
        { key: 'type', label: '处分类型', type: 'select', required: true, options: this.ctx.statusOptions.disciplineType },
        { key: 'reason', label: '违纪事由', type: 'textarea', required: true, placeholder: '请描述违纪事实与依据条款（不少于 5 个字）' },
        { key: 'decideDate', label: '决定日期', type: 'date', required: true },
        { key: 'docNo', label: '文号', type: 'text', placeholder: '如 学字〔2026〕12 号' }
      ]
    }
  },
  async created() {
    const cols = await getFieldColumns('disciplineList')
    if (cols.code === 0) this.columns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    const st = readListState(this.$route, FILTER_KEYS)
    this.filters = { ...EMPTY_FILTERS(), ...st.filters }
    this.pagination.page = st.page
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
    typeLabel(v) {
      return (this.ctx.statusOptions.disciplineType.find((o) => o.value === v) || {}).label || v
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
      writeListState(this.$router, this.$route, { page: this.pagination.page, filters: this.filters, filterKeys: FILTER_KEYS })
      const res = await getDisciplineRecords({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    /* 独立详情页（第一批交互改造）：携带编号 query 供刷新定位；列表 query 已同步，返回不丢筛选页码 */
    openDetail(row) {
      this.$router.push({ path: '/admin/campus-service/discipline/' + row.id, query: { code: row.code } })
    },
    async onToolbar(key) {
      if (key === 'create') {
        if (!this.studentsOptions.length) {
          const res = await getServiceStudents({ pageSize: 100 })
          if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
        }
        this.createForm = { visible: true, submitting: false, model: {} }
      } else if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('disciplineList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    async submitCreate() {
      this.createForm.submitting = true
      const res = await createDisciplineRecord(this.createForm.model)
      this.createForm.submitting = false
      if (res.code === 0) {
        toast.success('处分记录已录入，已按流程告知学生并写入审计日志')
        this.createForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openRevoke(row) {
      if (!this.can('campus.discipline.edit')) return
      this.revokeDialog = { visible: true, submitting: false, row }
    },
    async submitRevoke({ reason }) {
      this.revokeDialog.submitting = true
      const res = await updateDisciplineRecord(this.revokeDialog.row.id, { status: 'REVOKED', reason })
      this.revokeDialog.submitting = false
      if (res.code === 0) {
        toast.success('处分已解除，解除说明已留痕并同步学生360')
        this.revokeDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openVoid(row) {
      if (!this.can('campus.discipline.void')) return
      this.voidDialog = { visible: true, submitting: false, row }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidDisciplineRecord(this.voidDialog.row.id, { reason })
      this.voidDialog.submitting = false
      if (res.code === 0) {
        toast.success('处分记录已作废（逻辑删除），原因已留痕')
        this.voidDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    exportFn(payload) {
      return createExport('disciplineList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dsv-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
