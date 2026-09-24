<template>
  <ModulePageShell title="迎新材料审核" subtitle="身份证明 / 录取通知书 / 证件照 / 资助证明等材料核验" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新材料审核">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 份材料 · 审核动作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <p v-if="$route.query.batchId" class="ori-batch-context">当前限定工作台所选批次 <button type="button" @click="$router.push({ path: '/admin/orientation', query: { batchId: $route.query.batchId } })">返回工作台</button></p>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无待处理材料" />
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
        <template #cell-materialType="{ row }">{{ row.materialTypeLabel || labelOf('materialType', row.materialType) }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="materialTagType[row.status] || 'default'" :label="row.statusLabel || labelOf('materialStatus', row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 材料查看 -->
      <AppDrawer v-model:visible="viewVisible" :title="viewTarget ? `材料查看 · ${viewTarget.name}` : '材料查看'" mode="modal" size="large">
        <template v-if="viewTarget">
          <div class="ori-material-summary">
            <div><b>{{ viewTarget.materialTypeLabel || labelOf('materialType', viewTarget.materialType) }}</b><span>第 {{ viewTarget.submissionNo }} 版 · 提交于 {{ viewTarget.submitTime }}</span></div>
            <StatusTag :type="materialTagType[viewTarget.status] || 'default'" :label="viewTarget.statusLabel || labelOf('materialStatus', viewTarget.status)" dot />
          </div>
          <FilePreviewer v-if="viewTarget.fileId" :file="viewTarget" @error="onFileError" />
          <div v-else class="ori-file-unavailable">该历史材料尚未接入安全文件中心，请按学校现有核验方式查看原件。</div>
          <div v-if="viewTarget.returnReason" class="ori-reject-box">最近退回原因：{{ viewTarget.returnReason }}</div>
        </template>
        <template #footer>
          <div class="ori-issue-footer">
            <AppButton variant="danger" :disabled="!canOperate(viewTarget)" :title="operateTip(viewTarget)" @click="returnVisible = true">退回修改</AppButton>
            <AppButton variant="primary" :disabled="!canOperate(viewTarget)" :title="operateTip(viewTarget)" @click="doApprove(viewTarget)">审核通过</AppButton>
          </div>
        </template>
      </AppDrawer>

      <AppConfirmDialog
        v-model:visible="returnVisible"
        title="退回材料"
        :message="viewTarget ? `退回「${viewTarget.name}」提交的《${viewTarget.fileName}》，学生将收到补充通知。` : ''"
        type="warning"
        confirm-text="确认退回"
        require-reason
        reason-label="退回原因"
        reason-placeholder="请写明不合规内容与补充要求（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onReturnConfirm"
      />

      <AppConfirmDialog
        v-model:visible="batchApproveVisible"
        title="批量通过材料"
        :message="`确认通过选中的 ${batchTargets.length} 份材料？`"
        type="primary"
        confirm-text="确认批量通过"
        :submitting="submitting"
        @confirm="onBatchApproveConfirm"
      ><p v-if="batchError" role="alert">{{ batchError }}</p></AppConfirmDialog>
      <AppConfirmDialog
        v-model:visible="batchReturnVisible"
        title="批量退回材料"
        :message="`将退回选中的 ${batchTargets.length} 份材料，退回原因将统一发送给相关学生。`"
        type="warning"
        confirm-text="确认批量退回"
        require-reason
        reason-label="退回原因"
        :submitting="submitting"
        @confirm="onBatchReturnConfirm"
      ><p v-if="batchError" role="alert">{{ batchError }}</p></AppConfirmDialog>

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出审核记录"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="审核留痕 · 迎新材料" mode="modal" size="xlarge">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 6：/admin/orientation/materials 迎新材料审核（查看 / 通过 / 退回原因必填 / 批量 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { TableActionColumn, BatchActionBar, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { MATERIAL_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', materialType: '' })

export default {
  name: 'OrientationMaterialReviewView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppDrawer,
    AppButton,
    FilePreviewer,
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
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      viewVisible: false,
      viewTarget: null,
      returnVisible: false,
      batchApproveVisible: false,
      batchReturnVisible: false,
      batchTargets: [],
      batchError: '',
      reviewContext: 0,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      materialTagType: MATERIAL_TAG_TYPE
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
    reviewPerm() {
      return this.perms['orientation.material.review']
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名 / 文件名' },
        { key: 'status', label: '审核状态', type: 'select', options: this.statusOptions.materialStatus || [] },
        { key: 'materialType', label: '材料类型', type: 'select', options: this.statusOptions.materialType || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.material.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出审核记录', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '审核留痕' }
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
  watch: {
    '$route.query.batchId'() { this.changeContext() },
    '$route.query.orientationStudentId'() { this.changeContext() }
  },
  beforeUnmount() { this.reviewContext++ },
  async created() {
    await this.init()
  },
  methods: {
    changeContext() {
      this.reviewContext++
      this.viewVisible = this.returnVisible = this.batchApproveVisible = this.batchReturnVisible = false
      this.viewTarget = null
      this.batchTargets = []
      this.batchError = ''
      this.page = 1
      this.load()
    },
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || (value ? '待确认' : '—')
    },
    onFileError(error) {
      toast.error(error?.message || '材料暂时无法打开，请稍后重试')
    },
    canOperate(target) {
      if (this.submitting || !target || target.status !== 'UPLOADED') return false
      return this.reviewPerm ? this.reviewPerm.allowed : true
    },
    operateTip(target) {
      if (!target || target.status !== 'UPLOADED') return '仅待审核材料可操作'
      return this.reviewPerm && !this.reviewPerm.allowed ? this.reviewPerm.reason : ''
    },
    async init() {
      const [ctx, status, cols, batch, exp] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFieldColumns('materialList'),
        api.getBatchActions('materialList'),
        api.getExportOptions('materialList')
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
      const serial = this.queueSerial = (this.queueSerial || 0) + 1
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getMaterialReviewList({ ...this.filters, page: this.page, pageSize: this.pageSize, batchId: this.$route.query.batchId || undefined, orientationStudentId: this.$route.query.orientationStudentId || undefined })
        if (serial !== this.queueSerial) return
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        if (serial === this.queueSerial) this.error = e.message || '加载失败'
      } finally {
        if (serial === this.queueSerial) this.loading = false
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
        { key: 'view', label: '查看材料' },
        { key: 'approve', label: '通过', disabled: !this.canOperate(row), disabledReason: this.operateTip(row) },
        { key: 'return', label: '退回', danger: true, disabled: !this.canOperate(row), disabledReason: this.operateTip(row) },
        { key: 'student', label: '学生详情' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') {
        this.viewTarget = row
        this.viewVisible = true
      }
      if (key === 'approve') this.doApprove(row)
      if (key === 'return') {
        this.viewTarget = row
        this.returnVisible = true
      }
      if (key === 'student') this.$router.push({ path: `/admin/orientation/students/${row.studentId}`, query: { batchId: this.$route.query.batchId || undefined } })
    },
    async doApprove(row) {
      if (this.submitting || !this.canOperate(row)) return
      const context = this.reviewContext
      this.submitting = true
      try {
        const res = await api.approveOrientationMaterial(row.id, { expectedVersion: row.version })
        if (context !== this.reviewContext) return
        if (res.code === 0) {
          toast.success(`已通过《${row.fileName}》，已写入留痕`)
          this.viewVisible = false
          await this.load()
        } else toast.error(res.message)
      } finally { this.submitting = false }
    },
    async onReturnConfirm({ reason }) {
      if (this.submitting || !this.viewTarget) return
      const context = this.reviewContext
      this.submitting = true
      try {
        const res = await api.returnOrientationMaterial(this.viewTarget.id, { reason, expectedVersion: this.viewTarget.version })
        if (context !== this.reviewContext) return
        if (res.code === 0) {
          toast.success('材料已退回，原因已通知学生并留痕')
          this.returnVisible = false
          this.viewVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'MATERIAL' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (this.submitting || !this.selected.length) return
      this.batchError = ''
      const selectedIds = new Set(this.selected.map(String))
      this.batchTargets = this.rows.filter(row => selectedIds.has(String(row.id))).map(row => ({ id: row.id, version: row.version }))
      if (this.batchTargets.length !== selectedIds.size) return toast.error('部分选中材料已不在当前列表，请重新选择')
      if (key === 'batchApprove') this.batchApproveVisible = true
      if (key === 'batchReturn') this.batchReturnVisible = true
    },
    async onBatchApproveConfirm() {
      await this.reviewBatch(true)
    },
    async onBatchReturnConfirm({ reason }) {
      await this.reviewBatch(false, reason)
    },
    async reviewBatch(pass, reason = '') {
      if (this.submitting || !this.batchTargets.length) return
      const context = this.reviewContext
      this.submitting = true
      try {
        const res = await api.batchReviewOrientationMaterials(this.batchTargets, { pass, reason, shouldContinue: () => context === this.reviewContext })
        if (context !== this.reviewContext) return
        if (res.code === 0) {
          toast.success(`已批量${pass ? '通过' : '退回'} ${res.data.count} 份材料，操作已留痕`)
          this.batchApproveVisible = false
          this.batchReturnVisible = false
          await this.load()
        } else {
          this.batchError = res.message
          toast.error(res.message)
          const completed = new Set(res.data?.completedIds || [])
          this.batchTargets = this.batchTargets.filter(row => !completed.has(String(row.id)))
          if (completed.size) await this.load()
          this.selected = this.batchTargets.map(row => row.id)
        }
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('materialList', { ...payload, batchId: this.$route.query.batchId })
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';

.ori-material-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.ori-material-summary b,
.ori-material-summary span { display: block; }
.ori-material-summary span { margin-top: 4px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.ori-file-unavailable {
  padding: var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface-2);
  color: var(--text-secondary);
}
.ori-reject-box {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--warning-700);
}
.ori-issue-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
