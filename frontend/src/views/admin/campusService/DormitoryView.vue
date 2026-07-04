<template>
  <ModulePageShell
    title="宿舍服务"
    :subtitle="'住宿 ' + dormTotal + ' 条 · 异常 ' + exceptionTotal + ' 条'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'dorm' }" @click="switchTab('dorm')">住宿台账</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'exception' }" @click="switchTab('exception')">异常管理</button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        :title="tab === 'dorm' ? '没有符合条件的住宿记录' : '没有符合条件的异常记录'"
        description="可调整筛选条件，或确认当前角色所辖楼栋范围"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-room="{ row }">{{ row.room }}-{{ row.bed }}</template>
        <template #cell-status="{ row }">
          <StatusTag
            v-if="tab === 'dorm'"
            :type="row.status === 'IN' ? 'success' : 'default'"
            :label="dormStatusLabel(row.status)"
            dot
          />
          <StatusTag v-else :status="row.status" :label="exStatusLabel(row.status)" dot />
        </template>
        <template #cell-exceptionCount="{ row }">
          <StatusTag v-if="row.exceptionCount" type="warning" :label="row.exceptionCount + ' 次'" />
          <span v-else class="mp-note">0</span>
        </template>
        <template #cell-type="{ row }">
          <StatusTag :type="['NIGHT_OUT', 'NO_RETURN', 'DISCIPLINE'].includes(row.type) ? 'danger' : 'warning'" :label="row.typeLabel" />
        </template>
        <template #cell-actions="{ row }">
          <template v-if="tab === 'dorm'">
            <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + row.studentId)">学生服务</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('campus.dorm.edit') }" :title="reason('campus.dorm.edit')" @click="openEdit(row)">编辑</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('campus.dorm.markException') }" :title="reason('campus.dorm.markException')" @click="openMark(row)">标记异常</button>
          </template>
          <template v-else>
            <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + row.studentId)">学生服务</button>
            <button
              v-if="row.status !== 'COMPLETED'"
              class="mp-link"
              :class="{ 'is-disabled': !can('campus.dorm.handle') }"
              :title="reason('campus.dorm.handle')"
              @click="openHandle(row)"
            >
              跟进处理
            </button>
            <span v-else class="mp-note">{{ row.handler }}</span>
          </template>
        </template>
      </DataTable>

      <p class="mp-note">
        住宿台账来自后勤同步/导入；晚归、夜不归宿由门禁数据自动生成并支持人工标记。异常处理留痕，严重违纪可转违纪处分流程。导出住宿名单默认脱敏并含水印。
      </p>
    </div>

    <FormDrawer
      v-model:visible="dormForm.visible"
      v-model="dormForm.model"
      :title="dormForm.mode === 'create' ? '新增住宿记录' : '编辑住宿信息（' + dormForm.model.name + '）'"
      :fields="dormFields"
      :submitting="dormForm.submitting"
      @submit="submitDormForm"
    />

    <FormDrawer
      v-model:visible="markForm.visible"
      v-model="markForm.model"
      :title="'标记宿舍异常（' + markForm.name + '）'"
      :fields="markFields"
      :submitting="markForm.submitting"
      submit-text="确认标记"
      note="异常标记会生成待处理记录并通知辅导员；连续/严重异常建议转违纪处分或关怀转介。"
      @submit="submitMark"
    />

    <AppConfirmDialog
      v-model:visible="handleDialog.visible"
      type="primary"
      title="跟进处理宿舍异常"
      :message="(handleDialog.row ? handleDialog.row.code + ' · ' + handleDialog.row.typeLabel : '') + '：填写处理说明后可选择继续跟进或直接办结。'"
      confirm-text="提交处理"
      require-reason
      reason-label="处理说明"
      reason-placeholder="请填写处理过程与结果（如已联系学生/已维修验收），不少于 5 个字"
      show-notify
      notify-label="办结（勾选后状态置为已办结）"
      :submitting="handleDialog.submitting"
      @confirm="submitHandle"
    />

    <ImportDrawer v-model:visible="importVisible" :template="importTemplate" :validate-fn="importValidateFn" :confirm-fn="importConfirmFn" @done="load" />
    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="0" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 宿舍服务 / 异常管理（/admin/campus-service/dormitory）。
 * 闭环：住宿台账（新增/编辑/导入/导出）→ 标记异常 → 异常跟进处理（说明必填留痕）→ 办结。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { ImportDrawer, ExportDrawer, FormDrawer } from '@/modules/campusService/components'
import {
  getDormitoryRecords, createDormitoryRecord, updateDormitoryRecord, getDormitoryExceptions, markDormException, handleDormException,
  getFieldColumns, getImportTemplate, getExportOptions, validateImport, confirmImport, createExport, getServiceStudents
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', buildingId: '', status: '', type: '' })

export default {
  name: 'DormitoryView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, ImportDrawer, ExportDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'dorm',
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      dormTotal: 0,
      exceptionTotal: 0,
      dormColumns: [],
      studentsOptions: [],
      dormForm: { visible: false, mode: 'create', submitting: false, model: {} },
      markForm: { visible: false, submitting: false, name: '', model: {}, row: null },
      handleDialog: { visible: false, submitting: false, row: null },
      importVisible: false,
      importTemplate: null,
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      const base = [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 房间 / 编号' },
        { key: 'buildingId', label: '楼栋', type: 'select', options: f.buildings }
      ]
      if (this.tab === 'dorm') return [...base, { key: 'status', label: '住宿状态', type: 'select', options: o.dormStatus }]
      return [
        ...base,
        { key: 'type', label: '异常类型', type: 'select', options: o.dormExceptionType },
        { key: 'status', label: '处理状态', type: 'select', options: o.dormExceptionStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = [
        { key: 'create', permission: 'campus.dorm.create', label: '＋ 新增住宿记录', variant: 'primary', onlyDorm: true },
        { key: 'mark', permission: 'campus.dorm.markException', label: '标记异常', onlyException: true },
        { key: 'import', permission: 'campus.record.import', label: '导入住宿名单', onlyDorm: true },
        { key: 'export', permission: 'campus.dorm.export', label: '导出住宿名单' }
      ].filter((a) => (!a.onlyDorm || this.tab === 'dorm') && (!a.onlyException || this.tab === 'exception'))
      return list
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    columns() {
      if (this.tab === 'dorm') {
        return this.dormColumns.length
          ? this.dormColumns
          : [
              { key: 'name', title: '学生' },
              { key: 'building', title: '楼栋' },
              { key: 'room', title: '房间 / 床位' },
              { key: 'checkinDate', title: '入住时间' },
              { key: 'status', title: '状态' },
              { key: 'exceptionCount', title: '近30天异常' },
              { key: 'actions', title: '操作', width: '220px' }
            ]
      }
      return [
        { key: 'code', title: '异常编号' },
        { key: 'name', title: '学生' },
        { key: 'building', title: '楼栋 / 房间' },
        { key: 'type', title: '类型' },
        { key: 'happenTime', title: '发生时间' },
        { key: 'detail', title: '情况说明' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    },
    dormFields() {
      const f = this.ctx.filterOptions
      const fields = [
        { key: 'buildingId', label: '楼栋', type: 'select', required: true, options: f.buildings },
        { key: 'room', label: '房间', type: 'text', required: true, placeholder: '如 312' },
        { key: 'bed', label: '床位', type: 'text', required: true, placeholder: '如 2' },
        { key: 'checkinDate', label: '入住日期', type: 'date' }
      ]
      if (this.dormForm.mode === 'create') {
        return [{ key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions }, ...fields]
      }
      return [...fields, { key: 'status', label: '住宿状态', type: 'select', required: true, options: this.ctx.statusOptions.dormStatus }]
    },
    markFields() {
      const fields = [
        { key: 'type', label: '异常类型', type: 'select', required: true, options: this.ctx.statusOptions.dormExceptionType },
        { key: 'detail', label: '情况说明', type: 'textarea', required: true, placeholder: '请描述异常情况（不少于 5 个字）' }
      ]
      if (!this.markForm.row) {
        return [{ key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions }, ...fields]
      }
      return fields
    }
  },
  async created() {
    const cols = await getFieldColumns('dormList')
    if (cols.code === 0) this.dormColumns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    this.loadTotals()
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    dormStatusLabel(v) {
      return (this.ctx.statusOptions.dormStatus.find((o) => o.value === v) || {}).label || v
    },
    exStatusLabel(v) {
      return (this.ctx.statusOptions.dormExceptionStatus.find((o) => o.value === v) || {}).label || v
    },
    switchTab(tab) {
      this.tab = tab
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
      const [d, e] = await Promise.all([getDormitoryRecords({ pageSize: 1 }), getDormitoryExceptions({ pageSize: 1 })])
      if (d.code === 0) this.dormTotal = d.data.total
      if (e.code === 0) this.exceptionTotal = e.data.total
    },
    async load() {
      this.loading = true
      this.error = ''
      const fn = this.tab === 'dorm' ? getDormitoryRecords : getDormitoryExceptions
      const res = await fn({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async ensureStudents() {
      if (!this.studentsOptions.length) {
        const res = await getServiceStudents({ pageSize: 100 })
        if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
      }
    },
    async onToolbar(key) {
      if (key === 'create') {
        await this.ensureStudents()
        this.dormForm = { visible: true, mode: 'create', submitting: false, model: {} }
      } else if (key === 'mark') {
        await this.ensureStudents()
        this.markForm = { visible: true, submitting: false, name: '选择学生', model: {}, row: null }
      } else if (key === 'import') {
        if (!this.importTemplate) {
          const res = await getImportTemplate('dormList')
          if (res.code === 0) this.importTemplate = res.data
        }
        this.importVisible = true
      } else if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('dormList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    openEdit(row) {
      if (!this.can('campus.dorm.edit')) return
      this.dormForm = {
        visible: true,
        mode: 'edit',
        submitting: false,
        model: { id: row.id, name: row.name, buildingId: row.buildingId, room: row.room, bed: row.bed, checkinDate: row.checkinDate, status: row.status }
      }
    },
    async submitDormForm() {
      this.dormForm.submitting = true
      const m = this.dormForm.model
      const res =
        this.dormForm.mode === 'create'
          ? await createDormitoryRecord(m)
          : await updateDormitoryRecord(m.id, { buildingId: m.buildingId, room: m.room, bed: m.bed, checkinDate: m.checkinDate, status: m.status })
      this.dormForm.submitting = false
      if (res.code === 0) {
        toast.success(this.dormForm.mode === 'create' ? '住宿记录已新增，已写入审计日志' : '住宿信息已更新，变更已留痕')
        this.dormForm.visible = false
        this.loadTotals()
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openMark(row) {
      if (!this.can('campus.dorm.markException')) return
      this.markForm = { visible: true, submitting: false, name: row.name, model: { studentId: row.studentId }, row }
    },
    async submitMark() {
      this.markForm.submitting = true
      const res = await markDormException(this.markForm.model)
      this.markForm.submitting = false
      if (res.code === 0) {
        toast.success('异常已标记并生成待处理记录（已通知辅导员，已留痕）')
        this.markForm.visible = false
        this.loadTotals()
        if (this.tab === 'exception') this.load()
      } else {
        toast.error(res.message)
      }
    },
    openHandle(row) {
      if (!this.can('campus.dorm.handle')) return
      this.handleDialog = { visible: true, submitting: false, row }
    },
    async submitHandle({ reason, notify }) {
      this.handleDialog.submitting = true
      const res = await handleDormException(this.handleDialog.row.id, { note: reason, complete: notify })
      this.handleDialog.submitting = false
      if (res.code === 0) {
        toast.success(notify ? '异常已办结，处理说明已留痕' : '跟进已记录，状态更新为跟进中')
        this.handleDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    importValidateFn(fileName) {
      return validateImport('dormList', fileName)
    },
    importConfirmFn(payload) {
      return confirmImport('dormList', payload)
    },
    exportFn(payload) {
      return createExport('dormList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
