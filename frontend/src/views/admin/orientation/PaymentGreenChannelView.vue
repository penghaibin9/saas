<template>
  <ModulePageShell title="缴费 / 绿色通道" subtitle="缴费状态跟踪 · 绿色通道申请审批" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="缴费与绿色通道">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <div class="ori-cj-head">
        <div class="ori-tabs">
          <button type="button" class="ori-tabs__item" :class="{ 'is-active': tab === 'payment' }" @click="switchTab('payment')">缴费状态</button>
          <button type="button" class="ori-tabs__item" :class="{ 'is-active': tab === 'green' }" @click="switchTab('green')">绿色通道审批</button>
        </div>
        <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 条 · 审批全程留痕`" @action="onToolbar" />
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" :title="tab === 'payment' ? '暂无缴费数据' : '暂无绿色通道申请'" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-paymentStatus="{ row }">
          <StatusTag :type="paymentTagType[row.paymentStatus] || 'default'" :label="labelOf('paymentStatus', row.paymentStatus)" dot />
        </template>
        <template #cell-greenChannelStatus="{ row }">
          <StatusTag :type="greenTagType[row.greenChannelStatus] || 'default'" :label="labelOf('greenChannelStatus', row.greenChannelStatus)" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="greenTagType[row.status] || 'default'" :label="labelOf('greenChannelStatus', row.status)" dot />
        </template>
        <template #cell-applyAmount="{ row }">¥{{ row.applyAmount }}</template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 绿色通道详情 -->
      <AppDrawer v-model:visible="detailVisible" :title="detailTarget ? `绿色通道申请 · ${detailTarget.name}` : '申请详情'">
        <template v-if="detailTarget">
          <div class="ori-kv">
            <div class="ori-kv__item"><span class="ori-kv__label">申请类型</span><span class="ori-kv__value">{{ detailTarget.applyType }}</span></div>
            <div class="ori-kv__item"><span class="ori-kv__label">涉及金额</span><span class="ori-kv__value">¥{{ detailTarget.applyAmount }}</span></div>
            <div class="ori-kv__item"><span class="ori-kv__label">提交时间</span><span class="ori-kv__value">{{ detailTarget.submitTime }}</span></div>
            <div class="ori-kv__item">
              <span class="ori-kv__label">审批状态</span>
              <StatusTag :type="greenTagType[detailTarget.status] || 'default'" :label="labelOf('greenChannelStatus', detailTarget.status)" />
            </div>
          </div>
          <h4 class="ori-drawer-sub">申请附件</h4>
          <div v-for="a in detailTarget.attachments" :key="a" class="ori-attach">▤ {{ a }}</div>
          <div v-if="detailTarget.rejectReason" class="ori-reject-box">最近审批意见：{{ detailTarget.rejectReason }}</div>
          <div v-if="detailTarget.remark" class="ori-inline-note" style="margin-top: var(--space-2)">备注：{{ detailTarget.remark }}</div>
        </template>
        <template #footer>
          <div class="ori-issue-footer">
            <AppButton variant="danger" :disabled="!canOperate(detailTarget)" :title="operateTip(detailTarget)" @click="rejectVisible = true">驳回</AppButton>
            <AppButton variant="secondary" :disabled="!canOperate(detailTarget)" :title="operateTip(detailTarget)" @click="returnVisible = true">退回补充</AppButton>
            <AppButton variant="primary" :disabled="!canOperate(detailTarget)" :title="operateTip(detailTarget)" @click="approveVisible = true">审核通过</AppButton>
          </div>
        </template>
      </AppDrawer>

      <AppConfirmDialog
        v-model:visible="approveVisible"
        title="通过绿色通道申请"
        :message="detailTarget ? `确认通过「${detailTarget.name}」的${detailTarget.applyType}申请？通过后缴费环节解除阻塞。` : ''"
        type="primary"
        confirm-text="确认通过"
        :submitting="submitting"
        @confirm="onApprove"
      />
      <AppConfirmDialog
        v-model:visible="rejectVisible"
        title="驳回绿色通道申请"
        :message="detailTarget ? `驳回「${detailTarget.name}」的${detailTarget.applyType}申请，学生需按正常流程缴费。` : ''"
        type="danger"
        confirm-text="确认驳回"
        require-reason
        reason-label="驳回原因"
        reason-placeholder="请写明驳回依据（不少于 5 个字），将通知学生"
        :submitting="submitting"
        @confirm="onReject"
      />
      <AppConfirmDialog
        v-model:visible="returnVisible"
        title="退回补充材料"
        :message="detailTarget ? `退回「${detailTarget.name}」的申请，学生补充材料后可重新提交。` : ''"
        type="warning"
        confirm-text="确认退回"
        require-reason
        reason-label="退回原因"
        :submitting="submitting"
        @confirm="onReturn"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出缴费 / 绿色通道数据"
        :options="exportOpts"
        :selected-count="0"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="审批留痕 · 缴费与绿色通道">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 5：/admin/orientation/payment 缴费 / 绿色通道（双 Tab：缴费状态跟踪 + 绿色通道审批，驳回原因必填）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import { TableActionColumn, ExportDialog, AuditTrailPanel, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { PAYMENT_TAG_TYPE, GREEN_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', paymentStatus: '', status: '' })

export default {
  name: 'PaymentGreenChannelView',
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
    TableActionColumn,
    ExportDialog,
    AuditTrailPanel,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      tab: 'payment',
      loading: true,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      paymentColumns: [],
      greenColumns: [],
      exportOpts: {},
      detailVisible: false,
      detailTarget: null,
      approveVisible: false,
      rejectVisible: false,
      returnVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      paymentTagType: PAYMENT_TAG_TYPE,
      greenTagType: GREEN_TAG_TYPE
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
      const p = this.perms['orientation.payment.view']
      return p ? !p.allowed : false
    },
    reviewPerm() {
      return this.perms['orientation.greenchannel.review']
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      if (this.tab === 'payment') {
        return [
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
          { key: 'paymentStatus', label: '缴费状态', type: 'select', options: this.statusOptions.paymentStatus || [] }
        ]
      }
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 申请类型' },
        { key: 'status', label: '审批状态', type: 'select', options: this.statusOptions.greenChannelStatus || [] }
      ]
    },
    tableColumns() {
      const cols = this.tab === 'payment' ? this.paymentColumns : this.greenColumns
      return cols.filter((c) => c.default || c.locked).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.payment.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '批量导出', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '审批留痕' }
      ].filter(Boolean)
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    canOperate(target) {
      if (!target || !['SUBMITTED', 'REVIEWING'].includes(target.status)) return false
      return this.reviewPerm ? this.reviewPerm.allowed : true
    },
    operateTip(target) {
      if (!target || !['SUBMITTED', 'REVIEWING'].includes(target?.status)) return '该申请已完成审批'
      return this.reviewPerm && !this.reviewPerm.allowed ? this.reviewPerm.reason : ''
    },
    async init() {
      const [ctx, status, payCols, greenCols, exp] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFieldColumns('paymentList'),
        api.getFieldColumns('greenChannelList'),
        api.getExportOptions('paymentList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (payCols.code === 0) this.paymentColumns = payCols.data
      if (greenCols.code === 0) this.greenColumns = greenCols.data
      if (exp.code === 0) this.exportOpts = exp.data
      await this.load()
    },
    switchTab(tab) {
      if (this.tab === tab) return
      this.tab = tab
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const fn = this.tab === 'payment' ? api.getPaymentStatusList : api.getGreenChannelApplications
        const res = await fn({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
      if (this.tab === 'payment') {
        return [
          { key: 'student', label: '学生详情' },
          { key: 'green', label: '查看绿色通道', disabled: row.greenChannelStatus === 'NOT_APPLIED', disabledReason: '该生未申请绿色通道' }
        ]
      }
      return [
        { key: 'detail', label: '查看申请' },
        { key: 'approve', label: '通过', disabled: !this.canOperate(row), disabledReason: this.operateTip(row) },
        { key: 'reject', label: '驳回', danger: true, disabled: !this.canOperate(row), disabledReason: this.operateTip(row) }
      ]
    },
    onRowAction(key, row) {
      if (key === 'student') this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'green') {
        this.tab = 'green'
        this.filters = { ...EMPTY_FILTERS(), keyword: row.name }
        this.load()
      }
      if (key === 'detail') {
        this.detailTarget = row
        this.detailVisible = true
      }
      if (key === 'approve') {
        this.detailTarget = row
        this.approveVisible = true
      }
      if (key === 'reject') {
        this.detailTarget = row
        this.rejectVisible = true
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'GREEN_CHANNEL' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    async onApprove() {
      this.submitting = true
      try {
        const res = await api.approveGreenChannel(this.detailTarget.id, {})
        if (res.code === 0) {
          toast.success('申请已通过，缴费环节解除阻塞，已留痕')
          this.approveVisible = false
          this.detailVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onReject({ reason }) {
      this.submitting = true
      try {
        const res = await api.rejectGreenChannel(this.detailTarget.id, { reason })
        if (res.code === 0) {
          toast.success('申请已驳回，原因已通知学生并留痕')
          this.rejectVisible = false
          this.detailVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onReturn({ reason }) {
      this.submitting = true
      try {
        const res = await api.returnGreenChannel(this.detailTarget.id, { reason })
        if (res.code === 0) {
          toast.success('申请已退回补充，原因已通知学生并留痕')
          this.returnVisible = false
          this.detailVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport(this.tab === 'payment' ? 'paymentList' : 'paymentList', payload)
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';

.ori-cj-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.ori-drawer-sub {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.ori-attach {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-2);
  background: var(--bg-section-blue);
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
