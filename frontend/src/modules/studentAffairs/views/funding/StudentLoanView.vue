<template>
  <AppPageShell title="助学贷款" subtitle="生源地/校园地贷款登记 → 回执 → 核对 → 确认。所有推进动作由后端状态机与当前版本共同裁定。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="助学贷款台账">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载助学贷款台账..." @retry="load" @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">贷款办理台账</span>
          <h3 class="sa-summary-strip__title">先核对回执与学生信息，再按顺序推进到确认</h3>
          <p class="sa-summary-strip__text">页面只显示当前数据范围内记录。操作列展示当前状态允许的下一步，不需要老师猜流程。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.loan.manage')" code="studentAffairs.funding.loan.manage" :loading="acting === 'reg'" @click="formVisible = true">登记贷款</AppPermissionButton>
        </div>
      </div>

      <div class="sa-workflow-strip" aria-label="贷款办理流程">
        <div class="sa-workflow-step" data-step="1">登记学生、类型、学年和金额</div>
        <div class="sa-workflow-step" data-step="2">收到回执后核对银行和学生信息</div>
        <div class="sa-workflow-step" data-step="3">确认无误后完成贷款台账</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
        </div>
      </div>

      <AppSectionCard v-if="formVisible" class="sa-inline-workspace" title="登记助学贷款">
        <p class="ln-intro">请按正式贷款材料填写。银行卡只录入后4位，避免保存完整敏感卡号。</p>
        <div class="ln-grid">
          <div class="ln-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="ln-field"><span>类型 *</span><AppSelect v-model="form.loanType" :options="LOAN_TYPE_OPTIONS" /></label>
          <label class="ln-field"><span>学年 *</span><AppTextInput v-model="form.yearCode" :maxlength="9" placeholder="2025-2026" /></label>
          <label class="ln-field"><span>金额 *</span><AppNumberInput v-model="form.amount" :min="0.01" :max="999999999999.99" :precision="2" /></label>
          <label class="ln-field"><span>银行</span><AppTextInput v-model="form.bankName" :maxlength="100" placeholder="贷款经办银行" /></label>
          <label class="ln-field"><span>银行卡后4位</span><AppTextInput v-model="form.bankLast4" :maxlength="4" placeholder="仅填写4位数字" /></label>
        </div>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        <div class="ln-actions"><button type="button" class="ln-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.loan.manage')" code="studentAffairs.funding.loan.manage" :loading="acting === 'reg'" @click="register">登记</AppPermissionButton></div>
      </AppSectionCard>

      <AppSectionCard title="贷款办理台账">
        <p class="ln-section-hint">推进前请核对学生、贷款类型、学年和回执材料；已确认记录只保留查看。</p>
        <DataTable v-if="loans.length" :columns="loanColumns" :rows="loans" row-key="loanId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo || '' }}</div></template>
          <template #cell-loanType="{ row }">{{ row.loanType === 'ORIGIN' ? '生源地' : '校园地' }}</template>
          <template #cell-bank="{ row }">{{ row.bankName || '—' }} {{ row.bankLast4 ? ('****' + row.bankLast4) : '' }}</template>
          <template #cell-yearCode="{ row }">{{ row.yearCode || '—' }}</template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-status="{ row }"><StatusTag :type="lnType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton v-if="allowsAdvance(row)" :allowed="canBtn('studentAffairs.funding.loan.manage')" code="studentAffairs.funding.loan.manage" size="sm" :loading="acting === row.loanId" :disabled="!hasVersion(row)" @click="openAdvance(row)">{{ nextLabel(row.status) }}</AppPermissionButton>
            <span v-else class="ln-muted">{{ row.status === 'CONFIRMED' ? '已确认' : '—' }}</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无贷款记录。需要办理时，可从页面上方登记学生贷款。</p>
        <AppPagination v-if="pagination.total > pagination.pageSize" v-model:page="pagination.page" v-model:pageSize="pagination.pageSize" :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog v-model:visible="advanceDlg.visible" :title="nextLabel(advanceDlg.status)" type="warning"
      :message="advanceMessage" :confirm-text="nextLabel(advanceDlg.status)" :submitting="acting === advanceDlg.loanId" @confirm="advance" />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
  AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect,
  AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const NEXT = { REGISTERED: '上传回执', RECEIPT: '确认已核对', VERIFIED: '确认贷款' }
const LOAN_TYPE_OPTIONS = [{ value: 'ORIGIN', label: '生源地' }, { value: 'CAMPUS', label: '校园地' }]
const LOAN_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'loanType', title: '类型' }, { key: 'bank', title: '银行/卡' },
  { key: 'yearCode', title: '学年' }, { key: 'amount', title: '金额' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '140px' }
]

export default {
  name: 'StudentLoanView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
    AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect,
    StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      loanColumns: LOAN_COLUMNS, loading: true, acting: '', errorMessage: '', formError: '', loans: [], statusCounts: null,
      formVisible: false, form: this.blank(), pagination: { page: 1, pageSize: 50, total: 0 },
      advanceDlg: { visible: false, loanId: '', status: '', version: null }
    }
  },
  computed: {
    LOAN_TYPE_OPTIONS: () => LOAN_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    advanceMessage() { return ({ REGISTERED: '确认已收到贷款回执后推进。', RECEIPT: '确认回执与学生、银行和金额一致后推进。', VERIFIED: '确认后贷款进入终态并写入台账。' })[this.advanceDlg.status] || '' },
    metricCards() {
      const count = (key) => this.statusCounts === null ? '—' : Number(this.statusCounts[key] || 0)
      return [
        { key: 't', label: '贷款总数', value: this.statusCounts === null ? '—' : Number(this.statusCounts.ALL || 0), accent: 'primary' },
        { key: 'p', label: '待核对/回执', value: this.statusCounts === null ? '—' : count('REGISTERED') + count('RECEIPT'), accent: 'warning' },
        { key: 'c', label: '已确认', value: count('CONFIRMED'), accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    blank() { return { studentId: '', loanType: 'ORIGIN', bankName: '', bankLast4: '', yearCode: '', amount: null } },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    allowsAdvance(row) { return Array.isArray(row?.allowedActions) && row.allowedActions.includes('ADVANCE') },
    async load() {
      this.loading = true; this.errorMessage = ''
      const response = await studentAffairsApi.getLoans({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (response.code === 0 && response.data) {
        this.loans = response.data.items || []
        this.statusCounts = response.data.statusCounts || null
        this.pagination.total = response.data.total != null ? response.data.total : this.loans.length
      } else {
        this.loans = []; this.statusCounts = null; this.pagination.total = 0
        this.errorMessage = response.message || '贷款台账加载失败'
      }
      this.loading = false
    },
    async register() {
      const form = this.form
      const year = form.yearCode.trim()
      const last4 = form.bankLast4.trim()
      if (!form.studentId) { this.formError = '请选择学生'; return }
      if (!/^\d{4}-\d{4}$/.test(year) || Number(year.slice(5)) !== Number(year.slice(0, 4)) + 1) { this.formError = '学年格式应为连续的YYYY-YYYY'; return }
      if (last4 && !/^\d{4}$/.test(last4)) { this.formError = '银行卡后4位必须为4位数字'; return }
      if (form.amount == null || Number(form.amount) <= 0 || Number(form.amount) > 999999999999.99) { this.formError = '贷款金额应大于0且不超过999999999999.99'; return }
      this.formError = ''; this.acting = 'reg'
      const response = await studentAffairsApi.registerLoan({
        studentId: Number(form.studentId), loanType: form.loanType,
        bankName: form.bankName.trim() || undefined, bankLast4: last4 || undefined,
        yearCode: year, amount: String(form.amount)
      })
      this.acting = ''
      if (response.code === 0) { toast.success('贷款已登记'); this.formVisible = false; this.form = this.blank(); this.pagination.page = 1; await this.load() }
      else this.formError = response.message || '登记失败'
    },
    openAdvance(row) { if (this.allowsAdvance(row) && this.hasVersion(row)) this.advanceDlg = { visible: true, loanId: row.loanId, status: row.status, version: row.version } },
    async advance() {
      const dialog = this.advanceDlg
      this.acting = dialog.loanId
      const response = await studentAffairsApi.advanceLoan(dialog.loanId, dialog.version)
      this.acting = ''
      if (response.code === 0) { dialog.visible = false; toast.success('贷款状态已推进'); await this.load() }
      else { toast.error(response.message || '操作失败'); if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.load() }
    },
    nextLabel(status) { return NEXT[status] || '推进' },
    amountText(value) { return value == null || value === '' ? '—' : (typeof value === 'number' ? `¥${value}` : value) },
    lnType(status) { return ({ REGISTERED: 'default', RECEIPT: 'warning', VERIFIED: 'processing', CONFIRMED: 'success' })[status] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { align-items: stretch; }
.ln-intro,
.ln-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.ln-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.ln-field { display: flex; flex-direction: column; gap: 5px; min-width: 0; font-size: var(--font-size-sm); }
.ln-field > span { color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.ln-actions { display: flex; gap: var(--space-3); justify-content: flex-end; padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.ln-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.ln-muted { color: var(--text-tertiary); }
@media (max-width: 1100px) { .ln-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 720px) { .ln-grid { grid-template-columns: 1fr; } .ln-actions { justify-content: stretch; } .ln-actions > * { flex: 1; } }
@import '@/styles/module-page.css';
</style>
