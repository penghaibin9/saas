<template>
  <ModulePageShell
    title="绿色通道"
    subtitle="家庭经济困难新生缓缴 / 助学贷款审核闭环（提交 → 审核中 → 通过 / 退回 / 驳回）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="绿色通道审核"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 条绿色通道申请 · 审核动作全程留痕`" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无绿色通道申请" description="当前数据范围内没有待审核的绿色通道申请" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-applyAmount="{ row }">
          <span>¥ {{ Number(row.applyAmount || 0).toLocaleString() }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTagType[row.status] || 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        :require-reason="confirmConf.requireReason"
        :reason-label="confirmConf.reasonLabel"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/green-channels 绿色通道审核（通过 / 退回 / 驳回；真实走后端 /orientation/green-channels）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })
const STATUS_OPTIONS = [
  { value: 'SUBMITTED', label: '已提交' },
  { value: 'REVIEWING', label: '审核中' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'RETURNED', label: '已退回' },
  { value: 'REJECTED', label: '已驳回' }
]

export default {
  name: 'OrientationGreenChannelView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    EmptyState, LoadingState, ErrorState, AppConfirmDialog, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      confirmVisible: false, confirmMode: '', confirmRow: null,
      statusTagType: { SUBMITTED: 'warning', REVIEWING: 'primary', APPROVED: 'success', RETURNED: 'warning', REJECTED: 'danger' }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 申请类型' },
        { key: 'status', label: '审核状态', type: 'select', options: STATUS_OPTIONS }
      ]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'className', title: '班级' },
        { key: 'applyType', title: '申请类型' },
        { key: 'applyAmount', title: '申请金额' },
        { key: 'submitTime', title: '提交时间' },
        { key: 'status', title: '审核状态' },
        { key: 'reviewer', title: '审核人' },
        { key: 'actions', title: '操作' }
      ]
    },
    confirmConf() {
      const r = this.confirmRow
      const who = r ? `「${r.name}」的绿色通道申请` : ''
      if (this.confirmMode === 'approve') return { title: '通过绿色通道', message: `确认${who}审核通过？通过后该生可先报到、按缓缴处理。`, type: 'primary', confirmText: '确认通过', requireReason: false, reasonLabel: '' }
      if (this.confirmMode === 'return') return { title: '退回补充材料', message: `将${who}退回，请说明需补充的材料。`, type: 'danger', confirmText: '确认退回', requireReason: true, reasonLabel: '退回原因（≥5 字）' }
      if (this.confirmMode === 'reject') return { title: '驳回申请', message: `确认驳回${who}？`, type: 'danger', confirmText: '确认驳回', requireReason: true, reasonLabel: '驳回原因（≥5 字）' }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '' }
    }
  },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try {
        const res = await api.getGreenChannelApplications({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions(row) {
      const pending = ['SUBMITTED', 'REVIEWING'].includes(row.status)
      const dr = pending ? '' : '该申请已审结'
      return [
        { key: 'approve', label: '通过', disabled: !pending, disabledReason: dr },
        { key: 'return', label: '退回', disabled: !pending, disabledReason: dr },
        { key: 'reject', label: '驳回', disabled: !pending, disabledReason: dr }
      ]
    },
    onRowAction(key, row) { this.confirmMode = key; this.confirmRow = row; this.confirmVisible = true },
    async onConfirm(reason) {
      const row = this.confirmRow; if (!row) return
      let res
      if (this.confirmMode === 'approve') res = await api.approveGreenChannel(row.id, { remark: '' })
      else if (this.confirmMode === 'return') res = await api.returnGreenChannel(row.id, { reason })
      else if (this.confirmMode === 'reject') res = await api.rejectGreenChannel(row.id, { reason })
      if (res && res.code === 0) { toast.success('已处理'); this.confirmVisible = false; await this.load() }
      else toast.error((res && res.message) || '操作失败')
    }
  }
}
</script>
