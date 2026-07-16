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
          <AppSelect v-model="genBatchId" :options="batchOptions" placeholder="选择批次生成…" />
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
                  <AppPermissionButton code="studentAffairs.funding.disburse.manage" size="sm" :loading="acting===d.disbursementId" @click="openIssue(d)">标记发放</AppPermissionButton>
                  <AppPermissionButton v-if="d.bankStatus==='PENDING'" code="studentAffairs.funding.disburse.manage" size="sm" variant="secondary" danger @click="openFail(d)">置失败</AppPermissionButton>
                </template>
                <span v-else class="fd-dash">已发放</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无发放记录，选批次「生成发放台账」</td></tr>
          </tbody>
        </table>
        <AppPagination v-if="total > pageSize || page > 1" class="fd-pager" v-model:page="page" v-model:pageSize="pageSize"
                       :total="total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 标记发放 -->
    <AppDrawer v-model:visible="issueDrawer.visible" title="标记发放">
      <div class="sa-form">
        <AppFormItem label="发放批次号" hint="选填，由银行/财务系统提供">
          <AppTextInput v-model="issueDrawer.form.disburseNo" placeholder="如：DISB20251001" :disabled="acting===issueDrawer.id" />
        </AppFormItem>
        <AppFormItem label="银行卡号后4位" hint="仅存后4位，选填">
          <AppTextInput v-model="issueDrawer.form.bankLast4" placeholder="如：6688" :maxlength="4" :disabled="acting===issueDrawer.id" />
        </AppFormItem>
      </div>
      <template #footer>
        <button type="button" class="fd-btn" :disabled="acting===issueDrawer.id" @click="issueDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.funding.disburse.manage" :loading="acting===issueDrawer.id" @click="submitIssue">确认已发放</AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 置失败（原因必填，保留强制校验） -->
    <AppConfirmDialog
      v-model:visible="failDialog.visible"
      title="标记发放失败"
      message="将该条发放记录置为失败，需说明原因以便后续核对与重新发放。"
      type="danger"
      confirm-text="确认置失败"
      :require-reason="true"
      reason-label="失败原因（至少5字）"
      reason-placeholder="如：银行卡号有误 / 账户已注销"
      :submitting="acting===failDialog.id"
      @confirm="onFailConfirm"
    />
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPagination,
        AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待发放' },
  { key: 'ISSUED', label: '已发放' }, { key: 'FAILED', label: '发放失败' }
]

export default {
  name: 'FundingDisbursementView',
  components: { AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell,
               AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', items: [], batches: [], stats: {},
      activeStatus: '', statusFilters: STATUS_FILTERS, genBatchId: '',
      page: 1, pageSize: 20, total: 0,
      issueDrawer: { visible: false, id: '', form: { disburseNo: '', bankLast4: '' } },
      failDialog: { visible: false, id: '' }
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
    },
    batchOptions() {
      return this.batches.map((b) => ({ label: `${b.schoolYear} · ${this.typeLabel(b.projectType)}（${b.status}）`, value: b.batchId }))
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ds, bs, st] = await Promise.all([
        studentAffairsApi.getFundingDisbursements({ bankStatus: this.activeStatus, page: this.page, pageSize: this.pageSize }),
        studentAffairsApi.getFundingBatches({ pageSize: 200 }),
        studentAffairsApi.getDisbursementStats()
      ])
      if (ds.code === 0 && ds.data) {
        this.items = ds.data.items || []
        this.total = ds.data.total != null ? ds.data.total : this.items.length
      } else this.errorMessage = ds.message || '发放台账加载失败'
      this.batches = (bs.code === 0 && bs.data) ? (bs.data.items || []) : []
      this.stats = (st.code === 0 && st.data) ? st.data : {}
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.page = 1; this.load() },
    async generate() {
      this.acting = 'gen'
      const res = await studentAffairsApi.generateDisbursements(this.genBatchId)
      this.acting = ''
      if (res.code === 0) { toast.success(`已生成 ${res.data.generated || 0} 条发放记录`); this.page = 1; this.load() }
      else toast.error(res.message || '生成失败')
    },
    openIssue(d) {
      this.issueDrawer = { visible: true, id: d.disbursementId, form: { disburseNo: '', bankLast4: '' } }
    },
    async submitIssue() {
      const { id, form } = this.issueDrawer
      this.acting = id
      const res = await studentAffairsApi.issueDisbursement(id, {
        disburseNo: form.disburseNo.trim() || undefined,
        bankLast4: form.bankLast4.trim() || undefined
      })
      this.acting = ''
      if (res.code === 0) { toast.success('已标记发放'); this.issueDrawer.visible = false; this.load() } else toast.error(res.message || '标记失败')
    },
    openFail(d) {
      this.failDialog = { visible: true, id: d.disbursementId }
    },
    async onFailConfirm({ reason }) {
      const id = this.failDialog.id
      this.acting = id
      const res = await studentAffairsApi.failDisbursement(id, reason)
      this.acting = ''
      if (res.code === 0) { toast.success('已置失败'); this.failDialog.visible = false; this.load() } else toast.error(res.message || '操作失败')
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
.fd-gen :deep(.app-select) { min-width: 220px; }
.fd-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.fd-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fd-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fd-reason { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.fd-ops { display: flex; gap: 6px; }
.fd-dash { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.fd-pager { margin-top: var(--space-4); }
.sa-form { display: flex; flex-direction: column; gap: var(--space-1); }
.fd-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.fd-btn:hover { border-color: var(--border-dark); }
.fd-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
