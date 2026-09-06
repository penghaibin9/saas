<template>
  <AppPageShell
    title="助学贷款"
    subtitle="回执核验与贷款台账"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="助学贷款台账"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载助学贷款台账…" @retry="load" @back="$router.push('/admin/student-affairs/funding')">
      <AppSectionCard title="贷款办理台账" compact>
        <div class="ln-statusbar" aria-label="按办理状态筛选">
          <button v-for="item in quickStatuses" :key="item.value || 'ALL'" type="button" :class="{ active: filters.status === item.value }" @click="setStatus(item.value)"><span>{{ item.label }}</span><strong>{{ item.value ? count(item.value) : Number(statusCounts.ALL || 0) }}</strong></button>
          <AppPermissionButton code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" @click="openRegister">代登记</AppPermissionButton>
        </div>
        <div class="ln-toolbar">
          <AppTextInput v-model="filters.keyword" class="ln-search" type="search" placeholder="姓名、学号或经办银行" clearable @change="applyFilters" @clear="applyFilters" />
          <AppSelect v-model="filters.status" class="ln-filter" :options="statusOptions" @change="applyFilters" />
          <AppSelect v-model="filters.loanType" class="ln-filter" :options="typeOptions" @change="applyFilters" />
          <AppTextInput v-model="filters.yearCode" class="ln-year" placeholder="学年，如 2026-2027" :maxlength="9" @change="applyFilters" />
          <button type="button" class="ln-secondary" :disabled="loading" @click="applyFilters">查询</button>
        </div>

        <DataTable v-if="loans.length" :columns="loanColumns" :rows="loans" row-key="loanId">
          <template #cell-student="{ row }">
            <strong class="ln-main">{{ row.realName || `学生 ${row.studentId}` }}</strong>
            <small>{{ row.studentNo || '学号待核对' }}</small>
          </template>
          <template #cell-loan="{ row }">
            <strong>{{ typeLabel(row.loanType) }} · {{ row.yearCode || '学年待核对' }}</strong>
            <small>{{ row.bankName || '银行待补充' }}<template v-if="row.bankLast4"> · 尾号 {{ row.bankLast4 }}</template></small>
          </template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-receipt="{ row }">
            <span>{{ row.receiptCodeMasked || '未填写回执编号' }}</span>
            <button v-if="row.receiptFile" type="button" class="ln-file" :disabled="fileBusy === row.loanId" @click="openReceipt(row)">{{ row.receiptFile.fileName || '查看回执材料' }}</button>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.statusLabel || row.status" dot />
            <small v-if="row.reviewOpinion" class="ln-opinion">{{ row.reviewOpinion }}</small>
          </template>
          <template #cell-actions="{ row }">
            <div class="ln-actions">
              <AppPermissionButton v-if="allows(row, 'SUBMIT_RECEIPT')" code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" size="sm" variant="secondary" @click="openAction(row, 'SUBMIT_RECEIPT')">补录回执</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'VERIFY')" code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" size="sm" @click="openAction(row, 'VERIFY')">核验通过</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'RETURN')" code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" size="sm" variant="secondary" @click="openAction(row, 'RETURN')">退回</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'CONFIRM')" code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" size="sm" @click="openAction(row, 'CONFIRM')">确认台账</AppPermissionButton>
              <span v-if="!row.allowedActions?.length" class="ln-muted">只读</span>
            </div>
          </template>
        </DataTable>
        <div v-else class="ln-empty">
          <strong>{{ hasFilters ? '没有匹配的贷款记录' : '当前范围还没有贷款记录' }}</strong>
          <p>{{ hasFilters ? '调整筛选条件后再试。' : '学生提交电子回执后会自动进入待核验队列，也可由老师代登记纸质来件。' }}</p>
        </div>
        <AppPagination v-if="total > pageSize || page > 1" v-model:page="page" v-model:pageSize="pageSize" :total="total" :disabled="loading" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer v-model:visible="registerDrawer.visible" title="代登记助学贷款" subtitle="可先建档，收到电子回执后再补录。" mode="modal" size="large">
      <div class="ln-form">
        <AppInlineAlert type="info" description="同一学生同一学年限一笔；银行卡仅填后4位。" />
        <div class="ln-form-grid">
          <AppFormItem label="学生" required><AppStudentPicker v-model="registerDrawer.form.studentId" placeholder="按姓名 / 学号搜索" :disabled="saving" /></AppFormItem>
          <AppFormItem label="贷款类型" required><AppSelect v-model="registerDrawer.form.loanType" :options="typeOptions.slice(1)" :disabled="saving" /></AppFormItem>
          <AppFormItem label="贷款学年" required><AppTextInput v-model="registerDrawer.form.yearCode" :maxlength="9" placeholder="2026-2027" :disabled="saving" /></AppFormItem>
          <AppFormItem label="贷款金额（元）" required hint="高职当前政策区间 1000–20000 元"><AppNumberInput v-model="registerDrawer.form.amount" :min="1000" :max="20000" :precision="2" :disabled="saving" /></AppFormItem>
          <AppFormItem label="经办银行"><AppTextInput v-model="registerDrawer.form.bankName" :maxlength="100" placeholder="如：国家开发银行" :disabled="saving" /></AppFormItem>
          <AppFormItem label="银行卡后4位"><AppTextInput v-model="registerDrawer.form.bankLast4" :maxlength="4" placeholder="仅4位数字" :disabled="saving" /></AppFormItem>
          <AppFormItem class="ln-span2" label="电子回执编号" hint="选填；不填则保存为“待补回执”"><AppTextInput v-model="registerDrawer.form.receiptCode" :maxlength="64" placeholder="6-64位字母、数字或短横线" :disabled="saving" /></AppFormItem>
          <AppFormItem class="ln-span2" label="回执材料" hint="选填 PDF、图片或文档；高风险文件需安全扫描完成后才能提交。">
            <FileUploader biz-type="LOAN" :disabled="saving" button-text="选择回执材料" @uploaded="onUploaded('register', $event)" @error="onUploadError" />
            <div v-if="registerDrawer.form.receiptFile" class="ln-uploaded"><span>{{ registerDrawer.form.receiptFile.fileName }}</span><span>{{ registerDrawer.form.receiptFile.statusText }}</span><button v-if="!registerDrawer.form.receiptFile.readyForBusiness" type="button" @click="refreshUploaded('register')">检查状态</button></div>
          </AppFormItem>
        </div>
        <AppInlineAlert v-if="registerDrawer.errorMessage" type="danger" :description="registerDrawer.errorMessage" />
      </div>
      <template #footer><button type="button" class="ln-secondary" :disabled="saving" @click="registerDrawer.visible = false">取消</button><AppPermissionButton code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" :loading="saving" @click="submitRegister">保存登记</AppPermissionButton></template>
    </AppDrawer>

    <AppDrawer v-model:visible="actionDrawer.visible" :title="actionTitle" :subtitle="actionSubtitle" mode="modal" size="large">
      <div v-if="actionDrawer.row" class="ln-form">
        <div class="ln-context">
          <div><span>学生</span><strong>{{ actionDrawer.row.realName }} · {{ actionDrawer.row.studentNo }}</strong></div>
          <div><span>贷款</span><strong>{{ typeLabel(actionDrawer.row.loanType) }} · {{ actionDrawer.row.yearCode }} · {{ amountText(actionDrawer.row.amount) }}</strong></div>
          <div><span>回执</span><strong>{{ actionDrawer.row.receiptCodeMasked || '尚未填写' }}</strong></div>
        </div>
        <template v-if="actionDrawer.action === 'SUBMIT_RECEIPT'">
          <div class="ln-form-grid">
            <AppFormItem label="贷款类型" required><AppSelect v-model="actionDrawer.form.loanType" :options="typeOptions.slice(1)" :disabled="saving" /></AppFormItem>
            <AppFormItem label="贷款学年" required><AppTextInput v-model="actionDrawer.form.yearCode" :maxlength="9" :disabled="saving" /></AppFormItem>
            <AppFormItem label="贷款金额（元）" required><AppNumberInput v-model="actionDrawer.form.amount" :min="1000" :max="20000" :precision="2" :disabled="saving" /></AppFormItem>
            <AppFormItem label="经办银行"><AppTextInput v-model="actionDrawer.form.bankName" :maxlength="100" :disabled="saving" /></AppFormItem>
            <AppFormItem label="银行卡后4位"><AppTextInput v-model="actionDrawer.form.bankLast4" :maxlength="4" :disabled="saving" /></AppFormItem>
            <AppFormItem label="电子回执编号" required><AppTextInput v-model="actionDrawer.form.receiptCode" :maxlength="64" :placeholder="actionDrawer.row.receiptCodeMasked ? '留空则沿用原回执编号' : '请输入完整回执编号'" :disabled="saving" /></AppFormItem>
            <AppFormItem class="ln-span2" label="更新回执材料"><FileUploader biz-type="LOAN" :disabled="saving" button-text="选择新的回执材料" @uploaded="onUploaded('action', $event)" @error="onUploadError" /><div v-if="actionDrawer.form.receiptFile" class="ln-uploaded"><span>{{ actionDrawer.form.receiptFile.fileName }}</span><span>{{ actionDrawer.form.receiptFile.statusText }}</span><button v-if="!actionDrawer.form.receiptFile.readyForBusiness" type="button" @click="refreshUploaded('action')">检查状态</button></div></AppFormItem>
          </div>
        </template>
        <AppFormItem v-else-if="actionDrawer.action === 'RETURN'" label="退回原因（5-1000字）" required><AppTextarea v-model="actionDrawer.form.reason" :rows="4" :maxlength="1000" placeholder="写明学生需要修改的具体信息或材料" :disabled="saving" /></AppFormItem>
        <AppFormItem v-else-if="actionDrawer.action === 'VERIFY'" label="核验备注"><AppTextarea v-model="actionDrawer.form.reason" :rows="3" :maxlength="1000" placeholder="选填，如：已核对学生、学年、金额和电子回执" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-else type="warning" description="确认后该记录进入贷款台账终态。请先核对学生、学年、金额、回执编号和材料。" />
        <AppInlineAlert v-if="actionDrawer.errorMessage" type="danger" :description="actionDrawer.errorMessage" />
      </div>
      <template #footer><button type="button" class="ln-secondary" :disabled="saving" @click="actionDrawer.visible = false">取消</button><AppPermissionButton code="studentAffairs.funding.loan.manage" :allowed="canBtn('studentAffairs.funding.loan.manage')" :loading="saving" @click="submitAction">{{ actionConfirmText }}</AppPermissionButton></template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell, AppPagination,
  AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextarea, AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import FileUploader from '@/components/file/FileUploader.vue'
import { DataTable } from '@/components/business'
import { fileSdk } from '@/services/file/fileSdk'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const LOAN_COLUMNS = [
  { key: 'student', title: '学生', width: '145px' }, { key: 'loan', title: '贷款与银行' },
  { key: 'amount', title: '金额', width: '110px' }, { key: 'receipt', title: '电子回执' },
  { key: 'status', title: '状态', width: '160px' }, { key: 'actions', title: '下一步', align: 'right', width: '225px' }
]
const TYPES = [{ label: '全部类型', value: '' }, { label: '生源地贷款', value: 'ORIGIN' }, { label: '校园地贷款', value: 'CAMPUS' }]
const STATUSES = [
  { label: '全部状态', value: '' }, { label: '待补回执', value: 'REGISTERED' },
  { label: '待学校核验', value: 'RECEIPT' }, { label: '已退回修改', value: 'RETURNED' },
  { label: '已核验', value: 'VERIFIED' }, { label: '已确认', value: 'CONFIRMED' },
  { label: '已撤回', value: 'WITHDRAWN' }
]
const freshRegister = () => ({ studentId: '', loanType: 'ORIGIN', yearCode: '', amount: null, bankName: '', bankLast4: '', receiptCode: '', receiptFile: null })

export default {
  name: 'StudentLoanView',
  components: {
    AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell,
    AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppStudentPicker, AppTextarea,
    AppTextInput, DataTable, FileUploader, StatusTag: AppStatusTag
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loanColumns: LOAN_COLUMNS, typeOptions: TYPES, statusOptions: STATUSES,
      quickStatuses: [{ label: '全部', value: '' }, { label: '待核验', value: 'RECEIPT' }, { label: '待补回执', value: 'REGISTERED' }, { label: '已退回', value: 'RETURNED' }, { label: '已确认', value: 'CONFIRMED' }],
      loading: true, saving: false, fileBusy: '', loadSeq: 0, errorMessage: '', loans: [],
      statusCounts: {}, policy: { minAmount: '1000.00', maxAmount: '20000.00', basis: '' },
      filters: { keyword: '', status: '', loanType: '', yearCode: '' }, page: 1, pageSize: 20, total: 0,
      registerDrawer: { visible: false, form: freshRegister(), errorMessage: '' },
      actionDrawer: { visible: false, row: null, action: '', form: {}, errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    hasFilters() { return Object.values(this.filters).some(Boolean) },
    actionTitle() { return ({ SUBMIT_RECEIPT: '补录贷款回执', VERIFY: '核验贷款回执', RETURN: '退回学生修改', CONFIRM: '确认贷款台账' })[this.actionDrawer.action] || '处理贷款记录' },
    actionSubtitle() { return ({ SUBMIT_RECEIPT: '补齐电子回执后进入学校待核验队列。', VERIFY: '核对学生、学年、金额和回执材料。', RETURN: '退回后学生 PC 与小程序会显示具体修改意见。', CONFIRM: '确认校内回执台账完成，不代表银行已经放款。' })[this.actionDrawer.action] || '' },
    actionConfirmText() { return ({ SUBMIT_RECEIPT: '提交待核验', VERIFY: '确认核验通过', RETURN: '确认退回', CONFIRM: '确认台账' })[this.actionDrawer.action] || '确认' }
  },
  mounted() { this.load() },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    count(status) { return Number(this.statusCounts?.[status] || 0) },
    allows(row, action) { return Array.isArray(row?.allowedActions) && row.allowedActions.includes(action) },
    typeLabel(type) { return type === 'CAMPUS' ? '校园地贷款' : '生源地贷款' },
    statusTone(status) { return ({ REGISTERED: 'default', RECEIPT: 'warning', RETURNED: 'danger', VERIFIED: 'processing', CONFIRMED: 'success', WITHDRAWN: 'default' })[status] || 'default' },
    amountText(value) { return value === null || value === undefined || value === '' ? '—' : (Number.isFinite(Number(value)) ? `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : value) },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.errorMessage = ''
      try {
        const response = await studentAffairsApi.getLoans({ ...this.filters, keyword: this.filters.keyword.trim(), yearCode: this.filters.yearCode.trim(), page: this.page, pageSize: this.pageSize })
        if (seq !== this.loadSeq) return
        if (response.code !== 0 || !response.data) throw new Error(response.message || '贷款台账加载失败')
        this.loans = response.data.items || []; this.total = Number(response.data.total || 0)
        this.statusCounts = response.data.statusCounts || {}; this.policy = response.data.policy || this.policy
        const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize))
        if (this.page > lastPage) { this.page = lastPage; await this.load() }
      } catch (error) { if (seq === this.loadSeq) this.errorMessage = error.message || '贷款台账加载失败' }
      finally { if (seq === this.loadSeq) this.loading = false }
    },
    applyFilters() { this.page = 1; this.load() },
    setStatus(status) { this.filters.status = status; this.applyFilters() },
    openRegister() { this.registerDrawer = { visible: true, form: freshRegister(), errorMessage: '' } },
    validateFields(form, { requireReceipt = false } = {}) {
      const year = String(form.yearCode || '').trim(); const last4 = String(form.bankLast4 || '').trim(); const amount = Number(form.amount)
      if (!/^\d{4}-\d{4}$/.test(year) || Number(year.slice(5)) !== Number(year.slice(0, 4)) + 1) return '贷款学年应为连续的 YYYY-YYYY'
      if (!Number.isFinite(amount) || amount < 1000 || amount > 20000) return '高职学生年度贷款金额应在1000至20000元之间'
      if (last4 && !/^\d{4}$/.test(last4)) return '银行卡后4位必须为4位数字'
      const code = String(form.receiptCode || '').replace(/\s+/g, '')
      if (requireReceipt && !code && !this.actionDrawer.row?.receiptCodeMasked) return '请填写电子回执编号'
      if (code && !/^[A-Za-z0-9-]{6,64}$/.test(code)) return '电子回执编号应为6-64位字母、数字或短横线'
      if (form.receiptFile && !form.receiptFile.readyForBusiness) return '回执材料仍在安全检查，请稍后检查状态再提交'
      return ''
    },
    buildPayload(form) {
      return { loanType: form.loanType, yearCode: String(form.yearCode || '').trim(), amount: String(form.amount), bankName: String(form.bankName || '').trim() || undefined, bankLast4: String(form.bankLast4 || '').trim() || undefined, receiptCode: String(form.receiptCode || '').replace(/\s+/g, '') || undefined, receiptFileId: form.receiptFile?.fileId || undefined }
    },
    async submitRegister() {
      if (this.saving) return
      const form = this.registerDrawer.form
      if (!form.studentId) { this.registerDrawer.errorMessage = '请选择学生'; return }
      const error = this.validateFields(form)
      if (error) { this.registerDrawer.errorMessage = error; return }
      this.saving = true; this.registerDrawer.errorMessage = ''
      try {
        const response = await studentAffairsApi.registerLoan({ studentId: Number(form.studentId), ...this.buildPayload(form) })
        if (response.code !== 0) throw new Error(response.message || '贷款登记失败')
        toast.success(response.data?.status === 'RECEIPT' ? '贷款与回执已进入待核验队列' : '贷款已登记，等待补录回执')
        this.registerDrawer.visible = false; this.page = 1; await this.load()
      } catch (error) { this.registerDrawer.errorMessage = error.message || '贷款登记失败' }
      finally { this.saving = false }
    },
    openAction(row, action) {
      this.actionDrawer = { visible: true, row, action, errorMessage: '', form: { loanType: row.loanType, yearCode: row.yearCode, amount: Number(row.amount), bankName: row.bankName || '', bankLast4: row.bankLast4 || '', receiptCode: '', receiptFile: null, reason: '' } }
    },
    async submitAction() {
      if (this.saving || !this.actionDrawer.row) return
      const { row, action, form } = this.actionDrawer
      if (!this.allows(row, action)) { this.actionDrawer.errorMessage = '当前状态已变化，请刷新后重试'; return }
      if (action === 'SUBMIT_RECEIPT') { const error = this.validateFields(form, { requireReceipt: true }); if (error) { this.actionDrawer.errorMessage = error; return } }
      if (action === 'RETURN' && String(form.reason || '').trim().length < 5) { this.actionDrawer.errorMessage = '请填写至少5字的具体退回原因'; return }
      this.saving = true; this.actionDrawer.errorMessage = ''
      try {
        const body = { action, version: row.version, reason: String(form.reason || '').trim() || undefined, ...(action === 'SUBMIT_RECEIPT' ? this.buildPayload(form) : {}) }
        const response = await studentAffairsApi.actionLoan(row.loanId, body)
        if (response.code !== 0) throw new Error(response.message || '贷款记录处理失败')
        toast.success(({ SUBMIT_RECEIPT: '回执已提交待核验', VERIFY: '回执已核验', RETURN: '已退回学生修改', CONFIRM: '贷款台账已确认' })[action])
        this.actionDrawer.visible = false; await this.load()
      } catch (error) { this.actionDrawer.errorMessage = error.message || '贷款记录处理失败'; if (error.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.load() }
      finally { this.saving = false }
    },
    onUploaded(target, file) { const drawer = target === 'register' ? this.registerDrawer : this.actionDrawer; drawer.form.receiptFile = file; drawer.errorMessage = '' },
    onUploadError(error) { const message = error?.message || '回执材料上传失败'; if (this.actionDrawer.visible) this.actionDrawer.errorMessage = message; else this.registerDrawer.errorMessage = message },
    async refreshUploaded(target) {
      const drawer = target === 'register' ? this.registerDrawer : this.actionDrawer; const file = drawer.form.receiptFile
      if (!file?.fileId) return
      try { drawer.form.receiptFile = await fileSdk.metadata(file.fileId) } catch (error) { drawer.errorMessage = error.message || '文件状态检查失败' }
    },
    async openReceipt(row) {
      if (!row.receiptFile?.fileId || this.fileBusy) return
      this.fileBusy = row.loanId
      try { if (row.receiptFile.canPreview) await fileSdk.preview(row.receiptFile.fileId, row.receiptFile.fileName); else if (row.receiptFile.canDownload) await fileSdk.download(row.receiptFile.fileId, row.receiptFile.fileName); else throw new Error('回执材料尚未通过安全检查') }
      catch (error) { toast.error(error.message || '回执材料打开失败') }
      finally { this.fileBusy = '' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ln-statusbar { display: flex; gap: 6px; align-items: center; margin-bottom: 10px; }.ln-statusbar > button:not(:last-child) { display: inline-flex; gap: 7px; align-items: center; min-height: 32px; padding: 0 10px; border: 1px solid var(--border-light); border-radius: 8px; color: var(--text-secondary); background: transparent; cursor: pointer; }.ln-statusbar > button.active:not(:last-child) { border-color: var(--color-primary); color: var(--color-primary); background: var(--color-primary-light); }.ln-statusbar > button:last-child { margin-left: auto; }.ln-statusbar strong { font-size: 12px; }.ln-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }.ln-search { flex: 1 1 240px; }.ln-filter { flex: 0 1 150px; }.ln-year { flex: 0 1 160px; }.ln-secondary { min-height: 36px; padding: 0 15px; border: 1px solid var(--border-light); border-radius: var(--radius-md); color: var(--text-primary); background: var(--bg-card); cursor: pointer; }.ln-secondary:disabled { opacity: .55; cursor: not-allowed; }.ln-main,.ln-main + small,.ln-table strong,.ln-table small { display: block; }.ln-main + small,[data-key='loan'] small { display: block; margin-top: 3px; color: var(--text-secondary); font-size: 12px; }.ln-file { display: block; max-width: 190px; overflow: hidden; margin-top: 4px; padding: 0; border: 0; color: var(--color-primary); background: transparent; font: inherit; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }.ln-opinion { display: block; max-width: 150px; overflow: hidden; margin-top: 4px; color: var(--text-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.ln-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }.ln-muted { color: var(--text-tertiary); font-size: 12px; }.ln-empty { padding: 42px 20px; color: var(--text-secondary); text-align: center; }.ln-empty strong { color: var(--text-primary); }.ln-empty p { margin: 6px 0 0; font-size: 13px; }.ln-form { display: grid; gap: 14px; }.ln-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px 16px; }.ln-span2 { grid-column: 1 / -1; }.ln-uploaded { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 8px 10px; border: 1px solid var(--border-light); border-radius: 8px; color: var(--text-secondary); font-size: 12px; }.ln-uploaded span:first-child { color: var(--text-primary); }.ln-uploaded button { margin-left: auto; border: 0; color: var(--color-primary); background: transparent; cursor: pointer; }.ln-context { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; padding: 12px; border: 1px solid var(--border-light); border-radius: 10px; background: var(--bg-card); }.ln-context div { display: grid; gap: 4px; min-width: 0; }.ln-context span { color: var(--text-secondary); font-size: 11px; }.ln-context strong { overflow: hidden; color: var(--text-primary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 900px) { .ln-form-grid,.ln-context { grid-template-columns: 1fr; }.ln-span2 { grid-column: auto; } }
@media (max-width: 640px) { .ln-statusbar { align-items: stretch; flex-wrap: wrap; }.ln-statusbar > button:last-child { margin-left: 0; }.ln-toolbar > * { flex: 1 1 100%; } }
</style>
