<template>
  <AppPageShell
    title="资助发放台账"
    subtitle="按批次生成发放记录，登记银行发放结果。列表、统计和操作均遵守当前数据范围。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="资助发放台账"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载发放台账..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
        </div>
        <div class="fd-gen">
          <AppFundingBatchPicker v-model="genBatchId" class="fd-genpick" :options="batchOptions" placeholder="选择批次生成…" />
          <AppPermissionButton
            :allowed="canBtn('studentAffairs.funding.disburse.manage')"
            code="studentAffairs.funding.disburse.manage"
            :loading="acting === 'gen'"
            :disabled="!genBatchId || !!batchError"
            @click="openGenerate"
          >生成发放台账</AppPermissionButton>
        </div>
      </div>

      <AppInlineAlert v-if="secondaryError" type="warning" :description="secondaryError" />

      <AppSectionCard title="发放记录">
        <div class="fd-filters">
          <button
            v-for="filter in statusFilters"
            :key="filter.key"
            type="button"
            class="fd-chip"
            :class="{ 'is-on': activeStatus === filter.key }"
            @click="setStatus(filter.key)"
          >{{ filter.label }}</button>
        </div>
        <DataTable v-if="items.length" :columns="disbursementColumns" :rows="items" row-key="disbursementId">
          <template #cell-student="{ row }">
            <span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span>
            <div class="mp-cell-sub">{{ row.studentNo || '' }}</div>
          </template>
          <template #cell-projectType="{ row }">{{ typeLabel(row.projectType) }}</template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-bankLast4="{ row }">{{ row.bankLast4 ? ('****' + row.bankLast4) : '—' }}</template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusType(row.bankStatus)" :label="row.bankStatusLabel || row.bankStatus" dot />
            <em v-if="row.bankStatus === 'FAILED' && row.failReason" class="fd-reason">{{ row.failReason }}</em>
          </template>
          <template #cell-actions="{ row }">
            <div class="fd-ops">
              <AppPermissionButton
                v-if="allows(row, 'ISSUE')"
                :allowed="canBtn('studentAffairs.funding.disburse.manage')"
                code="studentAffairs.funding.disburse.manage"
                size="sm"
                :loading="acting === row.disbursementId"
                :disabled="!hasVersion(row)"
                @click="issue(row)"
              >标记发放</AppPermissionButton>
              <AppPermissionButton
                v-if="allows(row, 'FAIL')"
                :allowed="canBtn('studentAffairs.funding.disburse.manage')"
                code="studentAffairs.funding.disburse.manage"
                size="sm"
                variant="secondary"
                danger
                :disabled="!hasVersion(row)"
                @click="fail(row)"
              >置失败</AppPermissionButton>
              <span v-if="!allows(row, 'ISSUE') && !allows(row, 'FAIL')" class="fd-dash">{{ row.bankStatus === 'ISSUED' ? '已发放' : '—' }}</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无发放记录</p>
        <AppPagination
          v-if="pagination.total > pagination.pageSize"
          v-model:page="pagination.page"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          @change="loadRecords"
        />
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="genDlg.visible"
      title="生成资助发放台账"
      type="warning"
      message="系统会为所选批次全部已获资助学生生成待发放记录。该操作仅限全域管理员，重复请求不会重复生成。"
      confirm-text="确认生成"
      :submitting="acting === 'gen'"
      @confirm="generate"
    />

    <AppConfirmDialog
      v-model:visible="issDlg.visible"
      :title="`标记为已发放 · ${issDlg.who}`"
      type="primary"
      message="确认后将写入正式发放流水、学生成长时间线并发送到账通知。请依据银行回单填写批次号。"
      confirm-text="确认发放"
      :submitting="acting === issDlg.disbursementId"
      @confirm="submitIssue"
    >
      <AppFormItem label="发放批次号" required>
        <AppTextInput v-model="issDlg.disburseNo" placeholder="必填，如银行回单批次号" :maxlength="100" />
      </AppFormItem>
      <AppFormItem label="银行卡后 4 位">
        <AppTextInput v-model="issDlg.bankLast4" placeholder="选填，只填最后 4 位数字" :maxlength="4" />
        <p class="fd-hint">仅用于核对到账账户，系统只存后4位。严禁填写完整卡号。</p>
      </AppFormItem>
      <AppInlineAlert v-if="issDlg.error" type="danger" :description="issDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="failDlg.visible"
      :title="`标记发放失败 · ${failDlg.who}`"
      type="danger"
      confirm-text="确认置失败"
      require-reason
      :reason-min-length="5"
      reason-label="失败原因（5-500字）"
      message="置为失败后该笔记录可重新发放，失败原因会写入台账并通知学生当前正在处理中。"
      :submitting="acting === failDlg.disbursementId"
      @confirm="submitFail"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppFundingBatchPicker, AppGlobalState, AppInlineAlert,
  AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
  AppStatusTag, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const DISBURSEMENT_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'projectType', title: '项目' },
  { key: 'amount', title: '金额' }, { key: 'bankLast4', title: '卡号后4位' },
  { key: 'status', title: '发放状态' }, { key: 'actions', title: '操作', align: 'right', width: '190px' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待发放' },
  { key: 'ISSUED', label: '已发放' }, { key: 'FAILED', label: '发放失败' },
  { key: 'RETURNED', label: '银行退回' }
]

export default {
  name: 'FundingDisbursementView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppFundingBatchPicker, AppGlobalState, AppInlineAlert,
    AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
    StatusTag: AppStatusTag, AppTextInput, DataTable
  },
  data() {
    return {
      disbursementColumns: DISBURSEMENT_COLUMNS,
      statusFilters: STATUS_FILTERS,
      issDlg: { visible: false, disbursementId: '', who: '', disburseNo: '', bankLast4: '', error: '', version: null },
      failDlg: { visible: false, disbursementId: '', who: '', version: null },
      genDlg: { visible: false },
      loading: true,
      acting: '',
      errorMessage: '',
      batchError: '',
      statsError: '',
      items: [],
      batches: [],
      stats: null,
      activeStatus: '',
      genBatchId: '',
      pagination: { page: 1, pageSize: 50, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    secondaryError() { return [this.batchError, this.statsError].filter(Boolean).join('；') },
    batchOptions() {
      return this.batches.map((batch) => ({
        value: batch.batchId,
        label: `${batch.schoolYear} · ${this.typeLabel(batch.projectType)}（${batch.status}）`
      }))
    },
    metricCards() {
      const find = (key) => this.stats && (this.stats.byStatus || []).find((row) => row.key === key)
      const count = (key) => { const row = find(key); return row ? row.count : (this.stats ? 0 : '—') }
      const cards = [
        { key: 't', label: '发放记录数', value: this.stats ? this.stats.total : '—', accent: 'primary' },
        { key: 'i', label: '已发放', value: count('ISSUED'), accent: 'success' },
        { key: 'p', label: '待发放', value: count('PENDING'), accent: 'warning' },
        { key: 'f', label: '失败/退回', value: this.stats ? Number(count('FAILED') || 0) + Number(count('RETURNED') || 0) : '—', accent: 'risk' }
      ]
      if (this.stats && this.stats.issuedAmountTotal != null) {
        cards.push({ key: 'a', label: '已发放金额合计', value: `¥${this.stats.issuedAmountTotal}`, accent: 'primary' })
      }
      return cards
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    allows(row, action) {
      if (Array.isArray(row?.allowedActions)) return row.allowedActions.includes(action)
      const fallback = { PENDING: ['ISSUE', 'FAIL'], FAILED: ['ISSUE'], RETURNED: ['ISSUE', 'FAIL'] }
      return (fallback[row?.bankStatus] || []).includes(action)
    },
    async load() {
      this.loading = true
      await Promise.all([this.loadRecords(), this.loadBatches(), this.loadStats()])
      this.loading = false
    },
    async loadRecords() {
      this.errorMessage = ''
      const response = await studentAffairsApi.getFundingDisbursements({
        bankStatus: this.activeStatus,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (response.code !== 0 || !response.data) {
        this.items = []
        this.pagination.total = 0
        this.errorMessage = response.message || '发放台账加载失败'
        return
      }
      this.items = response.data.items || []
      this.pagination.total = response.data.total != null ? response.data.total : this.items.length
    },
    async loadBatches() {
      this.batchError = ''
      const response = await studentAffairsApi.getFundingBatches({ page: 1, pageSize: 200 })
      if (response.code === 0 && response.data) this.batches = response.data.items || []
      else { this.batches = []; this.batchError = response.message || '资助批次加载失败，暂不能生成发放台账' }
    },
    async loadStats() {
      this.statsError = ''
      const response = await studentAffairsApi.getDisbursementStats()
      if (response.code === 0 && response.data) this.stats = response.data
      else { this.stats = null; this.statsError = response.message || '发放统计加载失败' }
    },
    setStatus(key) {
      if (this.activeStatus === key) return
      this.activeStatus = key
      this.pagination.page = 1
      this.loadRecords()
    },
    openGenerate() { if (this.genBatchId && !this.batchError) this.genDlg.visible = true },
    async generate() {
      this.acting = 'gen'
      const response = await studentAffairsApi.generateDisbursements(this.genBatchId)
      this.acting = ''
      if (response.code === 0) {
        this.genDlg.visible = false
        toast.success(`已生成 ${response.data.generated || 0} 条，已有 ${response.data.existing || 0} 条`)
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else toast.error(response.message || '生成失败')
    },
    issue(row) {
      if (!this.allows(row, 'ISSUE') || !this.hasVersion(row)) return
      this.issDlg = {
        visible: true, disbursementId: row.disbursementId, version: row.version,
        who: row.realName || row.studentNo || '该笔', disburseNo: '', bankLast4: '', error: ''
      }
    },
    async submitIssue() {
      const dialog = this.issDlg
      const number = dialog.disburseNo.trim()
      const last4 = dialog.bankLast4.trim()
      if (number.length < 2 || number.length > 100) { dialog.error = '发放批次号需2-100字'; return }
      if (last4 && !/^\d{4}$/.test(last4)) { dialog.error = '银行卡后4位须为4位数字；请勿填写完整卡号'; return }
      dialog.error = ''
      this.acting = dialog.disbursementId
      const response = await studentAffairsApi.issueDisbursement(dialog.disbursementId, {
        disburseNo: number, bankLast4: last4 || undefined, version: dialog.version
      })
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success('已标记发放并通知学生')
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else {
        dialog.error = response.message || '标记失败'
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords()
      }
    },
    fail(row) {
      if (!this.allows(row, 'FAIL') || !this.hasVersion(row)) return
      this.failDlg = {
        visible: true, disbursementId: row.disbursementId, version: row.version,
        who: row.realName || row.studentNo || '该笔'
      }
    },
    async submitFail({ reason }) {
      const dialog = this.failDlg
      const text = (reason || '').trim()
      if (text.length < 5 || text.length > 500) { toast.error('失败原因需5-500字'); return }
      this.acting = dialog.disbursementId
      const response = await studentAffairsApi.failDisbursement(dialog.disbursementId, text, dialog.version)
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success('已置失败并通知学生')
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else {
        toast.error(response.message || '操作失败')
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords()
      }
    },
    typeLabel(type) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[type] || type || '' },
    amountText(amount) { return (amount == null || amount === '') ? '—' : (typeof amount === 'number' ? `¥${amount}` : amount) },
    statusType(status) { return ({ PENDING: 'warning', ISSUED: 'success', FAILED: 'danger', RETURNED: 'default' })[status] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.fd-gen { display: flex; gap: var(--space-2); align-items: center; }
.fd-genpick { width: 260px; }
.fd-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.fd-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fd-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fd-reason { display: block; color: var(--danger-600); font-size: var(--font-size-xs); margin-top: 2px; }
.fd-ops { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.fd-dash { color: var(--text-tertiary); }
.fd-hint { margin: var(--space-2) 0 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: repeat(2, minmax(0,1fr)); } .fd-gen { width: 100%; } .fd-genpick { flex: 1; } }
@import '@/styles/module-page.css';
</style>
