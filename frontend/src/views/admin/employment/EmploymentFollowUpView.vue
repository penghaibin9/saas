<template>
  <ModulePageShell title="就业跟进记录" subtitle="帮扶联系 / 岗位推荐 / 回访记录台账" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业跟进台账">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 条跟进记录 · 全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无跟进记录" description="可在未就业学生列表中对学生发起跟进" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-way="{ row }">{{ labelOf('followUpWay', row.way) }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="followTagType[row.status] || 'default'" :label="labelOf('followUpStatus', row.status)" />
        </template>
        <template #cell-content="{ row }">
          <span :title="row.content">{{ row.content }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新增 / 编辑跟进 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? '编辑跟进记录' : '新增跟进记录'"
        :fields="editFields"
        :model="editing"
        :submitting="submitting"
        submit-text="保存跟进"
        @submit="onEditSubmit"
      />

      <!-- 作废跟进 -->
      <DeleteConfirmDialog
        v-model:visible="voidVisible"
        title="作废跟进记录"
        :message="voidTarget ? `确认作废「${voidTarget.studentName}」${voidTarget.followTime} 的跟进记录？` : ''"
        :submitting="submitting"
        @confirm="onVoidConfirm"
      />

      <!-- 历史跟进 -->
      <AppDrawer v-model:visible="historyVisible" :title="historyTarget ? `历史跟进 · ${historyTarget.studentName}` : '历史跟进'">
        <div v-for="f in historyList" :key="f.id" class="emp-follow">
          <div class="emp-follow__head">
            <span>{{ f.followTime }} · {{ labelOf('followUpWay', f.way) }} · {{ f.operator }}</span>
            <StatusTag :type="followTagType[f.status] || 'default'" :label="labelOf('followUpStatus', f.status)" />
          </div>
          <div class="emp-follow__content">{{ f.content }}</div>
          <div class="emp-inline-note">结果:{{ f.result || '—' }} · 下一步:{{ f.nextPlan || '—' }}</div>
        </div>
        <EmptyState v-if="!historyList.length" title="暂无历史跟进" />
      </AppDrawer>

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出跟进记录"
        :options="exportOpts"
        :selected-count="0"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 跟进记录">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 7：/admin/employment/followups 就业跟进记录（新增 / 编辑 / 作废 / 历史 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { TableActionColumn, EditDrawer, ExportDialog, AuditTrailPanel, ColumnSettings, DeleteConfirmDialog, NoPermissionState } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { FOLLOWUP_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'EmploymentFollowUpView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppDrawer,
    TableActionColumn,
    EditDrawer,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    DeleteConfirmDialog,
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
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      exportOpts: {},
      students: [],
      editVisible: false,
      editing: null,
      voidVisible: false,
      voidTarget: null,
      historyVisible: false,
      historyTarget: null,
      historyList: [],
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      followTagType: FOLLOWUP_TAG_TYPE
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
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名 / 跟进内容' },
        { key: 'status', label: '跟进状态', type: 'select', options: this.statusOptions.followUpStatus || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const create = this.perms['employment.followup.create']
      const exp = this.perms['employment.followup.export']
      return [
        create && !create.visible
          ? null
          : { key: 'create', label: '新增跟进', variant: 'primary', disabled: create ? !create.allowed : false, disabledReason: create?.reason },
        exp && !exp.visible ? null : { key: 'export', label: '导出跟进记录', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
      ].filter(Boolean)
    },
    editFields() {
      const base = [
        { key: 'way', label: '跟进方式', type: 'select', options: this.statusOptions.followUpWay || [], required: true },
        { key: 'content', label: '跟进内容', type: 'textarea', required: true },
        { key: 'result', label: '跟进结果', type: 'text' },
        { key: 'nextPlan', label: '下一步计划', type: 'text' }
      ]
      if (!this.editing) {
        return [
          {
            key: 'studentId',
            label: '学生',
            type: 'select',
            required: true,
            options: this.students.map((s) => ({ value: s.id, label: `${s.name} · ${s.className}` }))
          },
          ...base
        ]
      }
      return base
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    async init() {
      const [ctx, status, cols, exp, students] = await Promise.all([
        api.getEmploymentContext(),
        api.getStatusOptions(),
        api.getFieldColumns('followUpList'),
        api.getExportOptions('followUpList'),
        api.getEmploymentStudents({ page: 1, pageSize: 100 })
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (exp.code === 0) this.exportOpts = exp.data
      if (students.code === 0) this.students = students.data.list
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await api.getFollowUpRecords({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
    rowActions(row) {
      const edit = this.perms['employment.followup.edit']
      const voidP = this.perms['employment.followup.void']
      const voided = row.status === 'VOIDED'
      return [
        { key: 'history', label: '历史跟进' },
        { key: 'edit', label: '编辑', disabled: (edit ? !edit.allowed : false) || voided, disabledReason: voided ? '已作废记录不可编辑' : edit?.reason },
        { key: 'void', label: '作废', danger: true, disabled: (voidP ? !voidP.allowed : false) || voided, disabledReason: voided ? '该记录已作废' : voidP?.reason }
      ]
    },
    onRowAction(key, row) {
      if (key === 'history') this.openHistory(row)
      if (key === 'edit') {
        this.editing = row
        this.editVisible = true
      }
      if (key === 'void') {
        this.voidTarget = row
        this.voidVisible = true
      }
    },
    async openHistory(row) {
      this.historyTarget = row
      const res = await api.getFollowUpRecords({ keyword: row.studentName, page: 1, pageSize: 50 })
      this.historyList = res.code === 0 ? res.data.list : []
      this.historyVisible = true
    },
    onToolbar(key) {
      if (key === 'create') {
        this.editing = null
        this.editVisible = true
      }
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'FOLLOWUP' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    async onEditSubmit(form) {
      this.submitting = true
      try {
        const res = this.editing ? await api.updateFollowUp(this.editing.id, form) : await api.createFollowUp(form)
        if (res.code === 0) {
          toast.success(this.editing ? '跟进记录已更新并留痕' : '跟进记录已保存并留痕')
          this.editVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onVoidConfirm({ reason }) {
      if (!this.voidTarget) return
      this.submitting = true
      try {
        const res = await api.voidFollowUp(this.voidTarget.id, { reason })
        if (res.code === 0) {
          toast.success('跟进记录已作废（逻辑删除），原因已留痕')
          this.voidVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('followUpList', payload)
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-follow {
  padding: var(--space-3) 0;
  border-bottom: 1px dashed var(--border-light);
}
.emp-follow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.emp-follow__content {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
}
</style>
