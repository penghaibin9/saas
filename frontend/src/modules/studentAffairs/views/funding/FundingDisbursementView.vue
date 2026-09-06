<template>
  <AppPageShell
    title="奖助发放登记"
    subtitle="按批次生成发放记录，登记银行发放结果。列表、统计、导出和操作均遵守当前数据范围。"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
    watermark-purpose="资助发放台账"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载发放台账..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <AppInlineAlert v-if="genBatchId && routeSource === 'publicity'" type="info" :description="`已承接公示批次 #${genBatchId}；下方记录、生成与导出保持同一批次上下文。`" />
      <p v-if="genBatchId" class="fd-scope-note">当前批次 #{{ genBatchId }} · 汇总、记录与导出使用同一批次。</p>
      <div class="sa-toolbar">
        <div class="fd-summary"><span v-for="card in metricCards" :key="card.key"><span>{{ card.label }}</span><strong>{{ card.value }}</strong></span></div>
        <div class="fd-gen">
          <AppPermissionButton
            :allowed="canBtn('studentAffairs.funding.disburse.manage')"
            code="studentAffairs.funding.disburse.manage"
            variant="secondary"
            :disabled="!!errorMessage"
            @click="openExport"
          >导出 Excel 台账</AppPermissionButton>
          <AppFundingBatchPicker v-model="genBatchId" class="fd-genpick" :options="batchOptions" placeholder="选择批次查看与办理" @change="onBatchContextChange" />
          <AppPermissionButton
            :allowed="canBtn('studentAffairs.funding.disburse.manage')"
            code="studentAffairs.funding.disburse.manage"
            :loading="acting === 'gen'"
            :disabled="!genBatchId || !!batchError || !!acting"
            @click="openGenerate"
          >生成发放台账</AppPermissionButton>
        </div>
      </div>

      <AppInlineAlert v-if="secondaryError" type="warning" :description="secondaryError" />

      <div v-if="exportJob" class="fd-export-job" role="status" aria-live="polite">
        <div>
          <div class="mp-cell-main">Excel 导出任务 #{{ exportJob.jobId || exportJob.id }}</div>
          <div class="mp-cell-sub">{{ exportStatusText }} · {{ exportJob.progress || 0 }}%<span v-if="exportJob.rowCount != null"> · {{ exportJob.rowCount }} 条</span></div>
        </div>
        <button v-if="exportJob.downloadable" type="button" class="fd-link" @click="downloadExport">下载 Excel</button>
        <button v-else-if="exportJob.status === 'FAILED' || exportJob.status === 'DEAD'" type="button" class="fd-link" @click="openExport">重新创建</button>
      </div>

      <AppSectionCard title="发放记录">
        <div class="fd-filters">
          <button
            v-for="filter in statusFilters"
            :key="filter.key"
            type="button"
            class="fd-chip"
            :class="{ 'is-on': activeStatus === filter.key }"
            :aria-pressed="activeStatus === filter.key"
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
          <template #cell-receipt="{ row }"><span>{{ row.disburseNo || '尚未登记' }}</span><small class="fd-date">{{ timeText(row.issuedAt) }}</small></template>
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
                :disabled="!!acting || recordsLoading || !hasVersion(row)"
                @click="issue(row)"
              >{{ row.bankStatus === 'FAILED' || row.bankStatus === 'RETURNED' ? '重新登记成功' : '登记成功' }}</AppPermissionButton>
              <AppPermissionButton
                v-if="allows(row, 'FAIL')"
                :allowed="canBtn('studentAffairs.funding.disburse.manage')"
                code="studentAffairs.funding.disburse.manage"
                size="sm"
                variant="secondary"
                danger
                :disabled="!!acting || recordsLoading || !hasVersion(row)"
                @click="fail(row)"
              >登记失败</AppPermissionButton>
              <span v-if="!allows(row, 'ISSUE') && !allows(row, 'FAIL')" class="fd-dash">{{ row.bankStatus === 'ISSUED' ? '已发放' : '—' }}</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无发放记录</p>
        <AppPagination
          v-if="pagination.total > 0"
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
      :message="`批次 ${genDlg.label || genDlg.batchId}：仅为已获资助且尚无台账的申请建立待登记记录，重复生成不会增加重复记录。`"
      confirm-text="确认生成"
      :submitting="acting === 'gen'"
      @confirm="generate"
    />

    <AppConfirmDialog
      v-model:visible="exportDlg.visible"
      title="导出资助发放台账"
      type="warning"
      message="导出会按当前发放状态筛选和你的数据范围生成 Excel。用途会写入水印和安全审计，请填写真实使用目的。"
      confirm-text="创建导出任务"
      :submitting="acting === 'export'"
      @confirm="createExport"
    >
<p class="fd-record-context">{{ exportDlg.batchId ? `批次 #${exportDlg.batchId}` : '当前负责范围的全部批次' }} · {{ statusFilters.find(f => f.key === exportDlg.bankStatus)?.label || '全部状态' }}</p>
      <AppFormItem label="导出用途" required>
        <AppTextInput v-model="exportDlg.purpose" placeholder="至少5字，如：财务发放结果复核归档" :maxlength="500" />
      </AppFormItem>
      <AppInlineAlert v-if="exportDlg.error" type="danger" :description="exportDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="issDlg.visible"
      :title="`登记发放成功 · ${issDlg.who}`"
      type="primary"
      message="请根据实际回单登记结果，确认后通知学生并记录办理时间。本系统不直接付款。"
      confirm-text="保存成功登记"
      :submitting="acting === issDlg.disbursementId"
      @confirm="submitIssue"
    >
      <p class="fd-record-context">申请 #{{ issDlg.applicationId }} · {{ issDlg.amount }} · 批次 #{{ issDlg.batchId }}</p>
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
      :title="`登记发放失败 · ${failDlg.who}`"
      type="danger"
      confirm-text="保存失败原因"
      require-reason
      :reason-min-length="5"
      reason-label="失败原因（5-500字）"
      :message="`申请 #${failDlg.applicationId} · 批次 #${failDlg.batchId} · ${amountText(failDlg.amount)}。请按银行回执登记失败原因，保存后通知学生，可在核对完成后重新登记结果。`"
      :submitting="acting === failDlg.disbursementId"
      @confirm="submitFail"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppFundingBatchPicker, AppGlobalState, AppInlineAlert,
  AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
  AppStatusTag, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { fundingExportApi } from '@/modules/studentAffairs/api/fundingExport.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'

const DISBURSEMENT_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'projectType', title: '项目' },
  { key: 'amount', title: '金额' }, { key: 'bankLast4', title: '卡号后4位' },
  { key: 'receipt', title: '登记回单' }, { key: 'status', title: '发放状态' }, { key: 'actions', title: '操作', align: 'right', width: '190px' }
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
    AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
    StatusTag: AppStatusTag, AppTextInput, DataTable
  },
  data() {
    return {
      disbursementColumns: DISBURSEMENT_COLUMNS,
      statusFilters: STATUS_FILTERS,
      issDlg: { visible: false, disbursementId: '', who: '', disburseNo: '', bankLast4: '', error: '', version: null },
      failDlg: { visible: false, disbursementId: '', who: '', version: null, applicationId: '', batchId: '', amount: null },
      genDlg: { visible: false, batchId: '', label: '' },
      exportDlg: { visible: false, purpose: '', error: '' },
      exportJob: null,
      exportPollTimer: null,
      loading: true, recordsLoading: false, recordSeq: 0, batchSeq: 0, statsSeq: 0, disposed: false,
      acting: '',
      errorMessage: '',
      batchError: '',
      statsError: '',
      items: [],
      batches: [],
      stats: null,
      activeStatus: '',
      genBatchId: '', routeProjectId: '', routeSource: '',
      pagination: { page: 1, pageSize: 50, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    secondaryError() { return [this.batchError, this.statsError].filter(Boolean).join('；') },
    exportStatusText() {
      const status = this.exportJob?.status || 'CREATED'
      return ({ CREATED: '等待处理', RUNNING: '正在生成', SUCCEEDED: '已完成', FAILED: '生成失败', DEAD: '多次失败，需处理', EXPIRED: '已过期', REVOKED: '已撤销' })[status] || (status ? '状态待确认' : '—')
    },
    batchOptions() {
      return this.batches.map((batch) => ({
        value: batch.batchId,
        label: `${batch.schoolYear} · ${batch.projectName || this.typeLabel(batch.projectType)} · #${batch.batchId}（${({ OPEN: '开放申请', CLOSED: '申请截止', DRAFT: '草稿' })[batch.status] || '状态待核对'}）`
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
  mounted() { this.applyRouteContext(); this.load() },
  watch: {
    '$route.query'(value, previous) {
      if (['batchId', 'projectId', 'source'].every(key => String(value?.[key] || '') === String(previous?.[key] || ''))) return
      this.applyRouteContext(); this.pagination.page = 1; this.validateBatchContext(); this.loadRecords(); this.loadStats()
    }
  },
  beforeUnmount() { this.disposed = true; this.recordSeq++; this.batchSeq++; this.statsSeq++; this.stopExportPolling() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyRouteContext() {
      const q = this.$route.query || {}
      const batchId = String(q.batchId || '').trim()
      this.genBatchId = batchId
      this.routeProjectId = String(q.projectId || '').trim()
      this.routeSource = String(q.source || '').trim()
    },
    onBatchContextChange() {
      const batch = this.batches.find((item) => String(item.batchId) === String(this.genBatchId))
      const query = { ...this.$route.query }
      if (this.genBatchId) query.batchId = String(this.genBatchId); else delete query.batchId
      if (batch?.projectId) query.projectId = String(batch.projectId); else delete query.projectId
      this.routeProjectId = String(query.projectId || '')
      this.$router.replace({ query }).catch(() => {})
      this.pagination.page = 1
      this.validateBatchContext(); this.loadRecords(); this.loadStats()
    },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    allows(row, action) {
      return Array.isArray(row?.allowedActions) && row.allowedActions.includes(action)
    },
    async load() {
      this.loading = true
      await Promise.all([this.loadRecords(), this.loadBatches(), this.loadStats()])
      this.loading = false
    },
    async loadRecords() {
      const seq = ++this.recordSeq
      this.recordsLoading = true
      this.errorMessage = ''
      const response = await studentAffairsApi.getFundingDisbursements({ batchId: this.genBatchId || undefined,
        bankStatus: this.activeStatus, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (seq !== this.recordSeq) return
      this.recordsLoading = false
      if (response.code !== 0 || !response.data) { this.errorMessage = response.message || '发放台账加载失败'; return }
      this.items = response.data.items || []; this.pagination.total = Number(response.data.total || 0)
      const last = Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
      if (this.pagination.page > last) { this.pagination.page = last; await this.loadRecords() }
    },
    validateBatchContext() {
      if (!this.genBatchId) { this.batchError = ''; return }
      const batch = this.batches.find(item => String(item.batchId) === String(this.genBatchId))
      this.batchError = !batch ? '承接的资助批次当前不可见，已停止自动回退到其他批次' :
        this.routeProjectId && String(batch.projectId) !== String(this.routeProjectId) ? '批次与项目上下文不一致，请返回资助工作台重新进入' : ''
    },
    async loadBatches() {
      const seq = ++this.batchSeq, all = []
      this.batchError = ''
      let page = 1
      while (true) {
        const response = await studentAffairsApi.getFundingBatches({ page, pageSize: 200 })
        if (seq !== this.batchSeq) return
        if (response.code !== 0 || !response.data) { this.batchError = response.message || '资助批次加载失败'; return }
        const rows = response.data.items || []; all.push(...rows)
        if (all.length >= Number(response.data.total || 0)) break
        if (!rows.length) { this.batchError = '批次列表发生变化，请刷新后重试'; return }
        page++
      }
      this.batches = all; this.validateBatchContext()
    },
    async loadStats() {
      const seq = ++this.statsSeq
      this.statsError = ''; this.stats = null
      if (!this.canBtn('studentAffairs.stats.view')) return
      const response = await studentAffairsApi.getDisbursementStats(this.genBatchId || undefined)
      if (seq !== this.statsSeq) return
      if (response.code === 0 && response.data) this.stats = response.data
      else this.statsError = response.message || '发放汇总暂不可用，仍可查看台账'
    },
    setStatus(key) {
      if (this.activeStatus === key) return
      this.activeStatus = key
      this.pagination.page = 1
      this.loadRecords()
    },
    openGenerate() { if (!this.acting && this.genBatchId && !this.batchError) this.genDlg = { visible: true, batchId: this.genBatchId, label: this.batchOptions.find(b => String(b.value) === String(this.genBatchId))?.label || this.genBatchId } },
    async generate() {
      if (this.acting || !this.genDlg.visible) return
      this.acting = 'gen'
      const response = await studentAffairsApi.generateDisbursements(this.genDlg.batchId)
      this.acting = ''
      if (response.code === 0) {
        this.genDlg.visible = false
        toast.success(`已生成 ${response.data.generated || 0} 条，已有 ${response.data.existing || 0} 条`)
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else toast.error(response.message || '生成失败')
    },
    openExport() {
      if (this.acting) return
      this.exportDlg = { visible: true, purpose: '', error: '', batchId: this.genBatchId, bankStatus: this.activeStatus }
    },
    async createExport() {
      if (this.acting) return
      const purpose = (this.exportDlg.purpose || '').trim()
      if (purpose.length < 5 || purpose.length > 500) {
        this.exportDlg.error = '导出用途需5-500字'
        return
      }
      this.exportDlg.error = ''
      this.acting = 'export'
      const response = await fundingExportApi.create({
        purpose,
        batchId: this.exportDlg.batchId || undefined,
        bankStatus: this.exportDlg.bankStatus || undefined
      })
      this.acting = ''
      if (response.code !== 0 || !response.data?.jobId) {
        this.exportDlg.error = response.message || '创建导出任务失败'
        return
      }
      this.exportDlg.visible = false
      this.exportJob = response.data
      toast.success('导出任务已创建，可继续使用系统')
      this.startExportPolling()
    },
    startExportPolling() {
      this.stopExportPolling()
      this.refreshExportJob()
      this.exportPollTimer = window.setInterval(this.refreshExportJob, 2500)
    },
    stopExportPolling() {
      if (this.exportPollTimer) window.clearInterval(this.exportPollTimer)
      this.exportPollTimer = null
    },
    async refreshExportJob() {
      const jobId = this.exportJob?.jobId || this.exportJob?.id
      if (!jobId) return
      const response = await fundingExportApi.job(jobId)
      if (this.disposed || String(this.exportJob?.jobId || this.exportJob?.id) !== String(jobId)) return
      if (response.code !== 0 || !response.data) {
        this.stopExportPolling()
        return
      }
      this.exportJob = { ...response.data, jobId }
      if (['SUCCEEDED', 'FAILED', 'DEAD', 'EXPIRED', 'REVOKED'].includes(this.exportJob.status)) {
        this.stopExportPolling()
        if (this.exportJob.status === 'SUCCEEDED') toast.success('资助发放台账已生成，可下载')
        else if (this.exportJob.status === 'FAILED' || this.exportJob.status === 'DEAD') toast.error(this.exportJob.errorMessage || '导出任务失败')
      }
    },
    async downloadExport() {
      const jobId = this.exportJob?.jobId || this.exportJob?.id
      if (!jobId) return
      const response = await fundingExportApi.ticket(jobId, this.exportJob.version)
      if (response.code !== 0 || !response.data?.downloadUrl) {
        toast.error(response.message || '创建下载票据失败')
        return
      }
      this.exportJob.version = response.data.version
      downloadXlsxFromApi({ filename: '资助发放台账.xlsx', downloadUrl: response.data.downloadUrl })
    },
    issue(row) {
      if (this.acting || !this.allows(row, 'ISSUE') || !this.hasVersion(row)) return
      this.issDlg = {
        visible: true, disbursementId: row.disbursementId, version: row.version,
        applicationId: row.applicationId, batchId: row.batchId, amount: this.amountText(row.amount), who: row.realName || row.studentNo || '该笔', disburseNo: '', bankLast4: '', error: ''
      }
    },
    async submitIssue() {
      if (this.acting) return
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
        toast.success('发放结果已登记并通知学生')
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else {
        dialog.error = response.message || '标记失败'
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords()
      }
    },
    fail(row) {
      if (this.acting || !this.allows(row, 'FAIL') || !this.hasVersion(row)) return
      this.failDlg = {
        visible: true, disbursementId: row.disbursementId, version: row.version,
        applicationId: row.applicationId, batchId: row.batchId, amount: row.amount,
        who: row.realName || row.studentNo || '该笔'
      }
    },
    async submitFail({ reason }) {
      if (this.acting) return
      const dialog = this.failDlg
      const text = (reason || '').trim()
      if (text.length < 5 || text.length > 500) { toast.error('失败原因需5-500字'); return }
      this.acting = dialog.disbursementId
      const response = await studentAffairsApi.failDisbursement(dialog.disbursementId, text, dialog.version)
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success('失败原因已登记并通知学生')
        await Promise.all([this.loadRecords(), this.loadStats()])
      } else {
        toast.error(response.message || '操作失败')
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords()
      }
    },
    timeText(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' },
    typeLabel(type) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[type] || (type ? '类型待确认' : '') },
    amountText(amount) { return (amount == null || amount === '') ? '—' : (typeof amount === 'number' ? `¥${amount}` : amount) },
    statusType(status) { return ({ PENDING: 'warning', ISSUED: 'success', FAILED: 'danger', RETURNED: 'default' })[status] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.fd-summary { display:flex;gap:12px 24px;flex-wrap:wrap;width:100%;padding:12px 0 }
.fd-summary>span { display:flex;align-items:baseline;gap:8px;color:var(--text-secondary);font-size:13px }.fd-summary strong { color:var(--text-primary);font-size:18px;font-variant-numeric:tabular-nums }
.fd-date { display:block;margin-top:4px;color:var(--text-tertiary);font-size:12px }.fd-record-context { padding:12px;border:1px solid var(--border-light);border-radius:10px;color:var(--text-secondary) }
.fd-scope-note { margin: 0 0 var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-sm); }
.fd-gen { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.fd-genpick { width: 260px; }
.fd-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.fd-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fd-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fd-reason { display: block; color: var(--danger-600); font-size: var(--font-size-xs); margin-top: 2px; }
.fd-ops { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.fd-dash { color: var(--text-tertiary); }
.fd-hint { margin: var(--space-2) 0 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.fd-export-job { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-3); border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--bg-card); }
.fd-link { border: 0; background: transparent; color: var(--color-primary); font: inherit; cursor: pointer; font-weight: 600; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: repeat(2, minmax(0,1fr)); } .fd-gen { width: 100%; justify-content: flex-start; } .fd-genpick { flex: 1; } }
@import '@/styles/module-page.css';
</style>
