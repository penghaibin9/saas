<template>
  <ModulePageShell title="未就业学生帮扶" subtitle="未就业名单 · 重点帮扶 · 跟进闭环" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="未就业帮扶">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名未就业学生 · 帮扶动作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="当前数据范围内没有未就业学生" description="全部学生就业去向均已落实" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        row-clickable
        @row-click="viewDetail"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-helpLevel="{ row }">
          <RiskTag v-if="row.helpLevel === 'KEY_HELP'" level="HIGH" label="重点帮扶" />
          <span v-else class="emp-inline-note">常规</span>
        </template>
        <template #cell-riskLevel="{ row }">
          <RiskTag :level="row.riskLevel" />
        </template>
        <template #cell-lastFollowUpTime="{ row }">
          <span :class="{ 'emp-overdue': isFollowOverdue(row) }">{{ row.lastFollowUpTime || '从未跟进' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新增跟进 -->
      <EditDrawer
        v-model:visible="followVisible"
        :title="followTarget ? `新增跟进 · ${followTarget.name}` : '新增跟进'"
        :fields="followFields"
        :model="null"
        :submitting="submitting"
        submit-text="保存跟进"
        @submit="onFollowSubmit"
      />

      <!-- 批量分配就业老师 -->
      <AppConfirmDialog
        v-model:visible="assignVisible"
        title="批量分配就业老师"
        :message="`将为选中的 ${selected.length} 名学生统一分配就业老师负责帮扶。`"
        type="primary"
        confirm-text="确认分配"
        :submitting="submitting"
        @confirm="onAssignConfirm"
      >
        <input v-model="assignTeacher" class="emp-assign-input" placeholder="请输入就业老师姓名" />
      </AppConfirmDialog>

      <!-- 标记已就业 -->
      <AppConfirmDialog
        v-model:visible="markEmployedVisible"
        title="标记已就业"
        :message="markTarget ? `确认将「${markTarget.name}」标记为已就业？记录将转为待核验状态。` : `确认将选中的 ${selected.length} 名学生标记为已就业？`"
        type="primary"
        confirm-text="确认标记"
        :submitting="submitting"
        @confirm="onMarkEmployedConfirm"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出未就业名单"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 未就业帮扶">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 6：/admin/employment/unemployed 未就业学生列表（跟进 / 帮扶 / 分配 / 批量 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { TableActionColumn, BatchActionBar, EditDrawer, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', helpLevel: '', riskLevel: '' })

export default {
  name: 'UnemployedStudentListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    RiskTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppDrawer,
    TableActionColumn,
    BatchActionBar,
    EditDrawer,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      selected: [],
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      followVisible: false,
      followTarget: null,
      assignVisible: false,
      assignTeacher: '',
      markEmployedVisible: false,
      markTarget: null,
      exportVisible: false,
      auditVisible: false,
      auditLogs: []
    }
  },
  computed: {
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
      const p = this.perms['employment.record.view']
      return p ? !p.allowed : false
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号' },
        { key: 'helpLevel', label: '帮扶级别', type: 'select', options: this.statusOptions.helpLevel || [] },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: this.statusOptions.riskLevel || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['employment.unemployed.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出未就业名单', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
      ].filter(Boolean)
    },
    batchBarActions() {
      return this.batchDefs
        .map((b) => {
          const p = this.perms[b.permission]
          if (p && !p.visible) return null
          return { ...b, disabled: p ? !p.allowed : false, disabledReason: p?.reason }
        })
        .filter(Boolean)
    },
    followFields() {
      return [
        { key: 'way', label: '跟进方式', type: 'select', options: this.statusOptions.followUpWay || [], required: true },
        { key: 'content', label: '跟进内容', type: 'textarea', required: true, placeholder: '本次联系 / 推荐 / 面谈的具体内容' },
        { key: 'result', label: '跟进结果', type: 'text' },
        { key: 'nextPlan', label: '下一步计划', type: 'text' }
      ]
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    isFollowOverdue(row) {
      return !row.lastFollowUpTime || row.helpLevel === 'KEY_HELP'
    },
    async init() {
      const [ctx, status, cols, batch, exp] = await Promise.all([
        api.getEmploymentContext(),
        api.getStatusOptions(),
        api.getFieldColumns('unemployedList'),
        api.getBatchActions('unemployedList'),
        api.getExportOptions('unemployedList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (exp.code === 0) this.exportOpts = exp.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getUnemployedStudents({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    viewDetail(row) {
      this.$router.push(`/admin/employment/students/${row.id}`)
    },
    rowActions(row) {
      const followP = this.perms['employment.followup.create']
      const markP = this.perms['employment.unemployed.markEmployed']
      const helpP = this.perms['employment.unemployed.markKeyHelp']
      return [
        { key: 'view', label: '详情' },
        { key: 'follow', label: '新增跟进', disabled: followP ? !followP.allowed : false, disabledReason: followP?.reason },
        { key: 'markEmployed', label: '标记已就业', disabled: markP ? !markP.allowed : false, disabledReason: markP?.reason },
        {
          key: 'markKeyHelp',
          label: '重点帮扶',
          disabled: (helpP ? !helpP.allowed : false) || row.helpLevel === 'KEY_HELP',
          disabledReason: row.helpLevel === 'KEY_HELP' ? '已是重点帮扶学生' : helpP?.reason
        }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') this.viewDetail(row)
      if (key === 'follow') {
        this.followTarget = row
        this.followVisible = true
      }
      if (key === 'markEmployed') {
        this.markTarget = row
        this.markEmployedVisible = true
      }
      if (key === 'markKeyHelp') this.doMarkKeyHelp([row.id])
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({})
      if (res.code === 0) this.auditLogs = res.data.list.filter((l) => ['RECORD', 'FOLLOWUP'].includes(l.bizType))
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchRemind') this.doBatchRemind()
      if (key === 'batchAssign') {
        this.assignTeacher = ''
        this.assignVisible = true
      }
      if (key === 'batchExport') this.exportVisible = true
    },
    async doBatchRemind() {
      const res = await api.batchRemindStudents(this.selected)
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生发送提醒，操作已留痕`)
    },
    async doMarkKeyHelp(ids) {
      const res = await api.markKeyHelp(ids)
      if (res.code === 0) {
        toast.success('已纳入重点帮扶，操作已留痕')
        this.load()
      } else toast.error(res.message)
    },
    async onAssignConfirm() {
      if (!this.assignTeacher.trim()) {
        toast.error('请输入就业老师姓名')
        return
      }
      this.submitting = true
      try {
        const res = await api.assignEmploymentTeacher(this.selected, { teacher: this.assignTeacher.trim() })
        if (res.code === 0) {
          toast.success(`已为 ${res.data.count} 名学生分配就业老师`)
          this.assignVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onMarkEmployedConfirm() {
      const ids = this.markTarget ? [this.markTarget.id] : this.selected
      this.submitting = true
      try {
        const res = await api.markEmployed(ids)
        if (res.code === 0) {
          toast.success(`已标记 ${res.data.count} 名学生为已就业（待核验）`)
          this.markEmployedVisible = false
          this.markTarget = null
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onFollowSubmit(form) {
      if (!this.followTarget) return
      this.submitting = true
      try {
        const res = await api.createFollowUp({ ...form, studentId: this.followTarget.id })
        if (res.code === 0) {
          toast.success('跟进记录已保存并留痕')
          this.followVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('unemployedList', payload)
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-overdue {
  color: var(--danger-600);
}
.emp-assign-input {
  width: 100%;
  height: 36px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
</style>
