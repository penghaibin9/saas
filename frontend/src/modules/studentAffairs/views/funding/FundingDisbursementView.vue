<template>
  <AppPageShell
    title="资助发放台账"
    subtitle="按批次为已获资助学生生成发放记录，登记银行发放状态。金额按角色脱敏，不显示银行卡全号。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="资助发放台账"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载发放台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <div class="fd-gen">
          <select v-model="genBatchId" class="fd-input">
            <option value="">选择批次生成…</option>
            <option v-for="b in batches" :key="b.batchId" :value="b.batchId">{{ b.schoolYear }} · {{ typeLabel(b.projectType) }}（{{ b.status }}）</option>
          </select>
          <AppPermissionButton code="studentAffairs.funding.disburse.manage" :loading="acting==='gen'" :disabled="!genBatchId" @click="generate">生成发放台账</AppPermissionButton>
        </div>
      </div>

      <AppSectionCard title="发放记录">
        <div class="fd-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="fd-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>项目</th><th>金额</th><th>卡号后4位</th><th>发放状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="d in items" :key="d.disbursementId">
              <td><strong>{{ d.realName || ('学生#' + d.studentId) }}</strong></td>
              <td>{{ typeLabel(d.projectType) }}</td>
              <td>{{ amountText(d.amount) }}</td>
              <td>{{ d.bankLast4 ? ('****' + d.bankLast4) : '—' }}</td>
              <td><StatusTag :type="statusType(d.bankStatus)" :label="d.bankStatusLabel || d.bankStatus" dot />
                <em v-if="d.bankStatus==='FAILED' && d.failReason" class="fd-reason">{{ d.failReason }}</em></td>
              <td class="fd-ops">
                <template v-if="d.bankStatus!=='ISSUED'">
                  <AppPermissionButton code="studentAffairs.funding.disburse.manage" size="sm" :loading="acting===d.disbursementId" @click="issue(d)">标记发放</AppPermissionButton>
                  <AppPermissionButton v-if="d.bankStatus==='PENDING'" code="studentAffairs.funding.disburse.manage" size="sm" variant="secondary" danger @click="fail(d)">置失败</AppPermissionButton>
                </template>
                <span v-else class="fd-dash">已发放</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无发放记录，选批次「生成发放台账」</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 标记发放：原为「批次号→银行卡后4位」2 连原生弹窗。
         银行卡后 4 位属敏感信息，走浏览器原生框既无格式约束、也无任何用途说明。 -->
    <AppConfirmDialog
      v-model:visible="issDlg.visible" :title="`标记为已发放 · ${issDlg.who}`" type="primary"
      confirm-text="确认发放" :submitting="acting === issDlg.disbursementId" @confirm="submitIssue"
    >
      <AppFormItem label="发放批次号">
        <AppTextInput v-model="issDlg.disburseNo" placeholder="可空；如银行回单批次号" :maxlength="64" />
      </AppFormItem>
      <AppFormItem label="银行卡后 4 位">
        <AppTextInput v-model="issDlg.bankLast4" placeholder="可空；只填最后 4 位数字" :maxlength="4" />
        <p class="fd-hint">仅用于核对到账账户，系统只存后 4 位，不存完整卡号。请勿填写完整卡号。</p>
      </AppFormItem>
      <AppInlineAlert v-if="issDlg.error" type="danger" :description="issDlg.error" />
    </AppConfirmDialog>

    <!-- 发放失败原因 -->
    <AppConfirmDialog
      v-model:visible="failDlg.visible" :title="`标记发放失败 · ${failDlg.who}`" type="danger"
      confirm-text="确认置失败" require-reason :reason-min-length="5" reason-label="失败原因（≥5 字）"
      description="置为失败后该笔发放可重新处理。原因将记入发放台账。"
      :submitting="acting === failDlg.disbursementId" @confirm="submitFail"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
  AppPermissionButton, AppSectionCard, AppStatusTag, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待发放' },
  { key: 'ISSUED', label: '已发放' }, { key: 'FAILED', label: '发放失败' }
]

export default {
  name: 'FundingDisbursementView',
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
    AppPermissionButton, AppSectionCard, AppTextInput, StatusTag: AppStatusTag
  },
  data() {
    return {
      issDlg: { visible: false, disbursementId: '', who: '', disburseNo: '', bankLast4: '', error: '' },
      failDlg: { visible: false, disbursementId: '', who: '' },
      loading: true, acting: '', errorMessage: '', items: [], batches: [], stats: {},
      activeStatus: '', statusFilters: STATUS_FILTERS, genBatchId: ''
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => (this.stats.byStatus || []).find((x) => x.key === k)
      const cnt = (k) => { const r = s(k); return r ? r.count : 0 }
      const cards = [
        { key: 't', label: '发放记录数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'i', label: '已发放', value: cnt('ISSUED'), accent: 'success' },
        { key: 'p', label: '待发放', value: cnt('PENDING'), accent: 'warning' }
      ]
      if (this.stats.issuedAmountTotal != null) cards.push({ key: 'a', label: '已发放金额合计', value: '¥' + this.stats.issuedAmountTotal, accent: 'primary' })
      return cards
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ds, bs, st] = await Promise.all([
        studentAffairsApi.getFundingDisbursements({ bankStatus: this.activeStatus, pageSize: 300 }),
        studentAffairsApi.getFundingBatches({ pageSize: 200 }),
        studentAffairsApi.getDisbursementStats()
      ])
      if (ds.code === 0 && ds.data) this.items = ds.data.items || []
      else this.errorMessage = ds.message || '发放台账加载失败'
      this.batches = (bs.code === 0 && bs.data) ? (bs.data.items || []) : []
      this.stats = (st.code === 0 && st.data) ? st.data : {}
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.load() },
    async generate() {
      this.acting = 'gen'
      const res = await studentAffairsApi.generateDisbursements(this.genBatchId)
      this.acting = ''
      if (res.code === 0) { toast.success(`已生成 ${res.data.generated || 0} 条发放记录`); this.load() }
      else toast.error(res.message || '生成失败')
    },
    issue(d) {
      this.issDlg = {
        visible: true, disbursementId: d.disbursementId, who: d.realName || d.studentNo || '该笔',
        disburseNo: '', bankLast4: '', error: ''
      }
    },
    async submitIssue() {
      const d = this.issDlg
      const last4 = d.bankLast4.trim()
      // 原生 prompt 对「仅存后4位」毫无约束，粘完整卡号也照单全收；这里挡在前面。
      if (last4 && !/^\d{4}$/.test(last4)) { d.error = '银行卡后 4 位须为 4 位数字；请勿填写完整卡号'; return }
      d.error = ''
      this.acting = d.disbursementId
      const res = await studentAffairsApi.issueDisbursement(d.disbursementId, {
        disburseNo: d.disburseNo.trim() || undefined, bankLast4: last4 || undefined
      })
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已标记发放'); this.load() }
      else { d.error = res.message || '标记失败' }
    },
    fail(d) {
      this.failDlg = { visible: true, disbursementId: d.disbursementId, who: d.realName || d.studentNo || '该笔' }
    },
    async submitFail({ reason }) {
      const d = this.failDlg
      this.acting = d.disbursementId
      const res = await studentAffairsApi.failDisbursement(d.disbursementId, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已置失败'); this.load() } else toast.error(res.message || '操作失败')
    },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t || '' },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) },
    statusType(s) { return ({ PENDING: 'warning', ISSUED: 'success', FAILED: 'danger', RETURNED: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.fd-gen { display: flex; gap: var(--space-2); align-items: center; }
.fd-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.fd-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.fd-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fd-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fd-reason { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.fd-ops { display: flex; gap: 6px; }
.fd-dash { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.fd-hint { margin: var(--space-1) 0 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
