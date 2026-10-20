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

      <p v-if="$route.query.batchId" class="ori-batch-context">当前限定工作台所选批次 <button type="button" @click="$router.push({ path: '/admin/orientation', query: { batchId: $route.query.batchId } })">返回工作台</button></p>
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
        <template #cell-submitTime="{ row }">{{ formatDateTime(row.submitTime) }}</template>
        <template #cell-remark="{ row }"><span>{{ row.remark || '未填写说明' }}</span><p v-if="row.rejectReason">审核意见：{{ row.rejectReason }}</p></template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppDrawer v-model:visible="reviewVisible" :title="reviewTarget ? `申请核对 · ${reviewTarget.name}` : '申请核对'" mode="modal" size="large">
        <template v-if="reviewTarget">
          <p>{{ reviewTarget.applyType }} · ¥ {{ reviewTarget.applyAmount }} · {{ reviewTarget.statusLabel }}</p>
          <h3>学生说明</h3><p>{{ reviewTarget.remark || '未填写说明' }}</p>
          <p v-if="reviewTarget.rejectReason">审核意见：{{ reviewTarget.rejectReason }}</p>
          <h3>证明材料</h3>
          <LoadingState v-if="proofLoading" />
          <ErrorState v-else-if="proofError" :description="proofError" @retry="loadProofs(reviewTarget)" />
          <p v-else-if="!proofFiles.length">未附证明材料</p>
          <template v-else>
            <nav aria-label="申请证明材料"><button v-for="file in proofFiles" :key="file.fileId" type="button" :aria-pressed="proofFile?.fileId === file.fileId" @click="proofFile = file">{{ file.fileName }}</button></nav>
            <FilePreviewer v-if="proofFile" :key="proofFile.fileId" :file="proofFile" @error="proofError = $event.message || '材料打开失败，请重试'" />
          </template>
        </template>
        <template #footer><button type="button" @click="reviewVisible = false">关闭核对</button></template>
      </AppDrawer>

      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        :require-reason="confirmConf.requireReason"
        :submitting="confirmSubmitting"
        :reason-label="confirmConf.reasonLabel"
        @confirm="onConfirm"
      >
        <dl v-if="confirmRow" class="ori-review-summary">
          <dt>申请类型与金额</dt><dd>{{ confirmRow.applyType }} · ¥ {{ confirmRow.applyAmount }}</dd>
          <dt>学生说明</dt><dd>{{ confirmRow.remark || '未填写说明' }}</dd>
          <template v-if="confirmRow.rejectReason"><dt>此前审核意见</dt><dd>{{ confirmRow.rejectReason }}</dd></template>
          <dt>证明材料</dt><dd>{{ confirmRow.attachments?.length ? confirmRow.attachments.join('、') : '未附证明材料' }}</dd>
        </dl>
      </AppConfirmDialog>
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/green-channels 绿色通道审核（通过 / 退回 / 驳回；真实走后端 /orientation/green-channels）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { formatDateTime } from '@/utils/dateUtils'
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
    EmptyState, LoadingState, ErrorState, AppConfirmDialog, AppDrawer, FilePreviewer, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      confirmVisible: false, confirmMode: '', confirmRow: null, confirmSubmitting: false,
      reviewVisible: false, reviewTarget: null, proofFiles: [], proofFile: null, proofLoading: false, proofError: '', proofSerial: 0,
      statusTagType: { SUBMITTED: 'warning', REVIEWING: 'primary', APPROVED: 'success', RETURNED: 'warning', REJECTED: 'danger' }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    reviewAllowed() { return this.perms['orientation.greenchannel.review']?.allowed === true },
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
        { key: 'remark', title: '申请说明与意见' },
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
  watch: { '$route.query.batchId'() { this.page = 1; this.load() } },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.load()
  },
  methods: {
    formatDateTime,
    async loadProofs(row) {
      const serial = ++this.proofSerial
      this.proofLoading = true; this.proofError = ''; this.proofFiles = []; this.proofFile = null
      try {
        const files = await fileSdk.list({bizType:'ORIENTATION_GREEN_CHANNEL',bizId:row.id})
        if (serial !== this.proofSerial) return
        this.proofFiles = files; this.proofFile = files[0] || null
      } catch (e) { if (serial === this.proofSerial) this.proofError = e.message || '材料读取失败，请重试' }
      finally { if (serial === this.proofSerial) this.proofLoading = false }
    },
    async load() {
      const serial = this.queueSerial = (this.queueSerial || 0) + 1
      this.loading = true; this.error = ''
      try {
        const res = await api.getGreenChannelApplications({ ...this.filters, page: this.page, pageSize: this.pageSize, batchId: this.$route.query.batchId || undefined })
        if (serial !== this.queueSerial) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      } catch (e) { if (serial === this.queueSerial) this.error = e.message || '加载失败' } finally { if (serial === this.queueSerial) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions(row) {
      const pending = this.reviewAllowed && ['SUBMITTED', 'REVIEWING'].includes(row.status)
      const dr = !this.reviewAllowed ? '当前岗位没有绿色通道审核权限' : pending ? '' : '该申请已审结'
      return [
        { key: 'view', label: '查看申请' },
        { key: 'approve', label: '通过', disabled: !pending, disabledReason: dr },
        { key: 'return', label: '退回', disabled: !pending, disabledReason: dr },
        { key: 'reject', label: '驳回', disabled: !pending, disabledReason: dr }
      ]
    },
    onRowAction(key, row) { if (key === 'view') { this.reviewTarget = row; this.reviewVisible = true; this.loadProofs(row); return }; this.confirmMode = key; this.confirmRow = row; this.confirmVisible = true },
    async onConfirm({ reason = '' } = {}) {
      const row = this.confirmRow; if (!row || this.confirmSubmitting) return
      this.confirmSubmitting = true
      try {
        let res
        if (this.confirmMode === 'approve') res = await api.approveGreenChannel(row.id, { remark: '', expectedVersion: row.version })
        else if (this.confirmMode === 'return') res = await api.returnGreenChannel(row.id, { reason, expectedVersion: row.version })
        else if (this.confirmMode === 'reject') res = await api.rejectGreenChannel(row.id, { reason, expectedVersion: row.version })
        if (res && res.code === 0) { toast.success('已处理'); this.confirmVisible = false; await this.load() }
        else toast.error((res && res.message) || '操作失败')
      } catch (e) { toast.error(e.message || '审核未完成，请重试') }
      finally { this.confirmSubmitting = false }
    }
  }
}
</script>
