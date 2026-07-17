<template>
  <AppPageShell title="助学贷款" subtitle="生源地/校园地贷款登记 → 回执上传 → 核对 → 确认。金额脱敏，银行卡仅存后4位。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="助学贷款台账">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.funding.loan.manage" :loading="acting==='reg'" @click="formVisible=true">登记贷款</AppPermissionButton>
      </div>
      <AppSectionCard v-if="formVisible" title="登记助学贷款">
        <div class="ln-grid">
          <div class="ln-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="ln-field"><span>类型</span><AppSelect v-model="form.loanType" :options="LOAN_TYPE_OPTIONS" placeholder="" /></label>
          <label class="ln-field"><span>银行</span><AppTextInput v-model="form.bankName" /></label>
          <label class="ln-field"><span>银行卡号（仅存后4位）</span><AppTextInput v-model="form.bankLast4" :maxlength="4" /></label>
          <label class="ln-field"><span>学年</span><AppTextInput v-model="form.yearCode" placeholder="2025-2026" /></label>
          <label class="ln-field"><span>金额</span><AppNumberInput v-model="form.amount" :min="0" /></label>
        </div>
        <div class="ln-actions"><button type="button" class="ln-btn" @click="formVisible=false">取消</button>
          <AppPermissionButton code="studentAffairs.funding.loan.manage" :loading="acting==='reg'" @click="register">登记</AppPermissionButton></div>
      </AppSectionCard>
      <AppSectionCard title="贷款台账">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>类型</th><th>银行/卡</th><th>学年</th><th>金额</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="l in loans" :key="l.loanId">
              <td><strong>{{ l.realName || ('#'+l.studentId) }}</strong></td>
              <td>{{ l.loanType==='ORIGIN'?'生源地':'校园地' }}</td>
              <td>{{ l.bankName || '—' }} {{ l.bankLast4 ? ('****'+l.bankLast4) : '' }}</td>
              <td>{{ l.yearCode || '—' }}</td>
              <td>{{ amountText(l.amount) }}</td>
              <td><StatusTag :type="lnType(l.status)" :label="l.statusLabel || l.status" dot /></td>
              <td><AppPermissionButton v-if="l.status!=='CONFIRMED'" code="studentAffairs.funding.loan.manage" size="sm" :loading="acting===l.loanId" @click="advance(l)">{{ nextLabel(l.status) }}</AppPermissionButton><span v-else class="ln-muted">已确认</span></td>
            </tr>
            <tr v-if="!loans.length"><td colspan="7" class="sa-empty">暂无贷款记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard,
  AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const NEXT = { REGISTERED: '上传回执', RECEIPT: '核对', VERIFIED: '确认' }
const LOAN_TYPE_OPTIONS = [{ value: 'ORIGIN', label: '生源地' }, { value: 'CAMPUS', label: '校园地' }]

export default {
  name: 'StudentLoanView',
  components: {
    AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput
  },
  data() { return { loading: true, acting: '', errorMessage: '', loans: [], formVisible: false, form: this.blank() } },
  computed: {
    LOAN_TYPE_OPTIONS: () => LOAN_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.loans.filter((l) => l.status === k).length
      return [
        { key: 't', label: '贷款总数', value: this.loans.length, accent: 'primary' },
        { key: 'p', label: '待核对/回执', value: s('REGISTERED') + s('RECEIPT'), accent: 'warning' },
        { key: 'c', label: '已确认', value: s('CONFIRMED'), accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    blank() { return { studentId: '', loanType: 'ORIGIN', bankName: '', bankLast4: '', yearCode: '', amount: null } },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getLoans()
      if (res.code === 0 && res.data) this.loans = res.data.items || []
      else this.errorMessage = res.message || '加载失败'
      this.loading = false
    },
    async register() {
      const f = this.form
      if (!f.studentId) { toast.error('请选择学生'); return }
      this.acting = 'reg'
      const res = await studentAffairsApi.registerLoan({ studentId: Number(f.studentId), loanType: f.loanType, bankName: (f.bankName || '').trim() || undefined, bankLast4: (f.bankLast4 || '').trim() || undefined, yearCode: (f.yearCode || '').trim() || undefined, amount: f.amount != null ? Number(f.amount) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已登记'); this.formVisible = false; this.form = this.blank(); this.load() } else toast.error(res.message || '登记失败')
    },
    async advance(l) {
      this.acting = l.loanId
      const res = await studentAffairsApi.advanceLoan(l.loanId)
      this.acting = ''
      if (res.code === 0) { toast.success('已推进'); this.load() } else toast.error(res.message || '操作失败')
    },
    nextLabel(s) { return NEXT[s] || '推进' },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) },
    lnType(s) { return ({ REGISTERED: 'default', RECEIPT: 'warning', VERIFIED: 'processing', CONFIRMED: 'success' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.ln-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.ln-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.ln-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ln-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.ln-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ln-muted { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics, .ln-grid { grid-template-columns: 1fr; } }
</style>
