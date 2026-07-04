<template>
  <ModulePageShell title="报到进度跟踪" subtitle="按环节跟踪新生报到进度 · 卡点事项闭环处理" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="报到进度跟踪">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名新生 · 卡点处理全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无进度数据" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-progress="{ row }">
          <div class="ori-progress-cell">
            <div class="ori-progress-track"><div class="ori-progress-bar" :style="{ width: progressWidth(row) }" /></div>
            <span>{{ row.progress }}</span>
          </div>
        </template>
        <template #cell-blockedStep="{ row }">
          <StatusTag v-if="row.blockedStep" type="danger" :label="row.blockedStepLabel || row.blockedStep" dot />
          <span v-else class="ori-inline-note">无卡点</span>
        </template>
        <template #cell-blockedReason="{ row }">
          <span class="ori-inline-note">{{ row.blockedReason || '—' }}</span>
        </template>
        <template #cell-reportStatus="{ row }">
          <StatusTag :type="reportTagType[row.reportStatus] || 'default'" :label="labelOf('reportStatus', row.reportStatus)" />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 卡点详情 / 编辑 -->
      <AppDrawer v-model:visible="issueVisible" :title="issueTarget ? `卡点事项 · ${issueTarget.name}` : '卡点事项'">
        <template v-if="issueTarget">
          <div class="ori-issue-view">
            <div class="ori-kv__item">
              <span class="ori-kv__label">当前进度</span>
              <span class="ori-kv__value">{{ issueTarget.progress }}（{{ labelOf('reportStatus', issueTarget.reportStatus) }}）</span>
            </div>
            <label class="ori-issue-field">
              <span class="ori-kv__label">卡点环节</span>
              <select v-model="issueForm.blockedStep" class="ori-issue-control" :disabled="!canEditProgress">
                <option value="">无卡点</option>
                <option v-for="s in steps" :key="s.key" :value="s.key">{{ s.label }}</option>
              </select>
            </label>
            <label class="ori-issue-field">
              <span class="ori-kv__label">卡点说明</span>
              <textarea v-model="issueForm.blockedReason" class="ori-issue-control ori-issue-control--area" rows="3" :disabled="!canEditProgress" placeholder="说明阻塞原因与待办事项" />
            </label>
          </div>
        </template>
        <template #footer>
          <div class="ori-issue-footer">
            <AppButton
              variant="secondary"
              :disabled="!canManualResolve || !issueTarget?.blockedStep"
              :title="!canManualResolve ? resolveReason : ''"
              @click="onResolve"
            >
              标记人工已处理
            </AppButton>
            <AppButton variant="primary" :disabled="!canEditProgress" :title="!canEditProgress ? editReason : ''" :loading="submitting" @click="onIssueSave">
              保存卡点
            </AppButton>
          </div>
        </template>
      </AppDrawer>

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出进度报表"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 报到进度">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 4：/admin/orientation/progress 报到进度跟踪（卡点查看/编辑 / 人工处理 / 批量提醒 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppDrawer, AppButton } from '@/components/ui'
import { TableActionColumn, BatchActionBar, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { REPORT_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', blockedOnly: '' })

export default {
  name: 'RegistrationProgressView',
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
    AppButton,
    TableActionColumn,
    BatchActionBar,
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
      steps: [],
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      issueVisible: false,
      issueTarget: null,
      issueForm: { blockedStep: '', blockedReason: '' },
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      reportTagType: REPORT_TAG_TYPE
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
      const p = this.perms['orientation.student.view']
      return p ? !p.allowed : false
    },
    canEditProgress() {
      const p = this.perms['orientation.progress.edit']
      return p ? p.allowed : true
    },
    editReason() {
      return this.perms['orientation.progress.edit']?.reason || ''
    },
    canManualResolve() {
      const p = this.perms['orientation.progress.manualResolve']
      return p ? p.allowed : true
    },
    resolveReason() {
      return this.perms['orientation.progress.manualResolve']?.reason || ''
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
        {
          key: 'blockedOnly',
          label: '卡点情况',
          type: 'select',
          options: [
            { value: 'YES', label: '仅看有卡点' },
            { value: 'NO', label: '仅看无卡点' }
          ]
        }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.progress.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出进度报表', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
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
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    progressWidth(row) {
      const [done, all] = String(row.progress || '0/7').split('/').map(Number)
      if (!all) return '0%'
      return `${Math.round((done / all) * 100)}%`
    },
    async init() {
      const [ctx, status, cols, batch, exp, steps] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFieldColumns('progressList'),
        api.getBatchActions('progressList'),
        api.getExportOptions('progressList'),
        api.getRegistrationSteps()
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (exp.code === 0) this.exportOpts = exp.data
      if (steps.code === 0) this.steps = steps.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getRegistrationProgress({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
      return [
        { key: 'issue', label: row.blockedStep ? '查看卡点' : '登记卡点' },
        { key: 'detail', label: '学生详情' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'detail') this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'issue') {
        this.issueTarget = row
        this.issueForm = { blockedStep: row.blockedStep || '', blockedReason: row.blockedReason || '' }
        this.issueVisible = true
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'PROGRESS' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchRemind') this.doBatchRemind()
    },
    async doBatchRemind() {
      const res = await api.batchRemindStudents(this.selected, '报到进度提醒（未完成环节）')
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名新生发送提醒，操作已留痕`)
    },
    async onIssueSave() {
      if (!this.issueTarget) return
      if (this.issueForm.blockedStep && (!this.issueForm.blockedReason || this.issueForm.blockedReason.trim().length < 5)) {
        toast.error('卡点说明不少于 5 个字')
        return
      }
      this.submitting = true
      try {
        const res = await api.updateBlockedIssue(this.issueTarget.id, this.issueForm)
        if (res.code === 0) {
          toast.success('卡点事项已更新并留痕')
          this.issueVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onResolve() {
      if (!this.issueTarget) return
      const res = await api.resolveBlockedIssue(this.issueTarget.id, {})
      if (res.code === 0) {
        toast.success('已标记人工处理，环节置为完成并留痕')
        this.issueVisible = false
        this.load()
      } else toast.error(res.message)
    },
    exportFn(payload) {
      return api.createExport('progressList', payload)
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';

.ori-progress-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 140px;
}
.ori-progress-track {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  overflow: hidden;
}
.ori-progress-bar {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--primary-400), var(--primary-600));
}
.ori-issue-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.ori-issue-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ori-issue-control {
  height: 36px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.ori-issue-control--area {
  height: auto;
  padding: var(--space-2);
  resize: vertical;
  font-family: inherit;
}
.ori-issue-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
