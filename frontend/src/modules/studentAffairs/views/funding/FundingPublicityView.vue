<template>
  <AppPageShell title="奖助公示确认" subtitle="核对公示期限与申诉情况，确认后进入发放准备。"
    :role-name="ctx?.currentRole?.roleName || ''" :data-scope-name="ctx?.dataScope?.scopeName || ''" watermark-purpose="资助公示确认">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载公示名单..." @retry="load" @back="backToFunding">
      <div class="fp-toolbar">
        <div><strong>{{ batchId ? `当前批次 #${batchId}` : '当前负责范围' }}</strong><span class="fp-total">公示中 {{ total }} 人</span></div>
        <div class="fp-tools"><button class="fp-link" :disabled="busy" @click="load">刷新</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" code="studentAffairs.funding.publicity.manage"
            :disabled="busy || total === 0" @click="openScan">批量确认到期申请</AppPermissionButton></div>
      </div>
      <div v-if="scanResult" class="fp-result" role="status"><strong>本次办理结果</strong><p>{{ scanResult }}</p><span>未通过核验的申请仍保留在公示名单，可核查原因后再次办理。</span></div>
      <AppSectionCard title="公示名单">
        <DataTable v-if="items.length" :columns="publicityColumns" :rows="items" row-key="applicationId">
          <template #cell-student="{ row }"><strong>{{ row.realName || '姓名待核对' }}</strong><small>{{ row.studentNo || '—' }} · 申请 #{{ row.applicationId }}</small></template>
          <template #cell-projectType="{ row }">{{ typeLabel(row.projectType) }}<small>批次 #{{ row.batchId }}</small></template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-deadline="{ row }">{{ timeText(row.publicityEnd) }}</template>
          <template #cell-progress="{ row }"><StatusTag :type="row.hasPendingAppeal ? 'warning' : row.publicityReady ? 'success' : 'info'" :label="row.publicityHint || '请刷新核对公示状态'" dot /></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton v-if="row.allowedActions?.includes('PUBLICITY_CONFIRM')" :allowed="canBtn('studentAffairs.funding.publicity.manage')"
              code="studentAffairs.funding.publicity.manage" size="sm" variant="secondary" :disabled="busy" @click="openConfirm(row)">确认获资助</AppPermissionButton>
            <button v-else-if="row.hasPendingAppeal" class="fp-link" @click="goAppeals(row)">查看申诉</button>
            <span v-else class="fp-muted">等待办理条件</span>
          </template>
        </DataTable>
        <div v-else class="fp-empty"><strong>{{ total ? '当前页已无待办' : '当前范围暂无公示待办' }}</strong><p>{{ total ? '名单已有变化，请返回上一页查看。' : '后续评审通过的申请仍会进入公示，不能据此判断整个批次结束。' }}</p></div>
        <AppPagination v-model:page="page" v-model:pageSize="pageSize" :total="total" @change="load" />
      </AppSectionCard>
      <div v-if="batchId" class="fp-next">
        <div><strong>本批次下一步</strong><p>评审或补正中 {{ unfinishedCount }} 人 · 已获资助 {{ grantedCount }} 人。发放台账仅接收已确认的申请。</p></div>
        <button v-if="grantedCount > 0" class="fp-link" @click="goDisbursement">查看本批次发放台账 →</button>
      </div>
    </AppGlobalState>
    <AppConfirmDialog v-model:visible="dialog.visible" :title="dialog.kind === 'scan' ? '批量确认到期申请' : `确认获资助 · ${dialog.row?.realName || ''}`"
      confirm-text="核对无误，确认获资助" :submitting="busy" @confirm="submitConfirmation">
      <div class="fp-dialog-context" v-if="dialog.kind === 'scan'"><strong>{{ dialog.batchId ? `批次 #${dialog.batchId}` : '当前账号负责范围内的全部批次' }}</strong><p>逐条核验公示期限、申诉、资格和额度；符合条件的申请将确认获资助。</p></div>
      <div class="fp-dialog-context" v-else><strong>{{ dialog.row?.studentNo }} · 申请 #{{ dialog.row?.applicationId }}</strong><p>{{ typeLabel(dialog.row?.projectType) }} · {{ amountText(dialog.row?.amount) }}</p><p>公示截止：{{ timeText(dialog.row?.publicityEnd) }}</p></div>
      <p class="fp-muted">确认后进入发放准备，本次操作不会直接付款。</p>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, AppPagination } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'projectType', title: '资助项目' }, { key: 'amount', title: '金额' },
  { key: 'deadline', title: '公示截止' }, { key: 'progress', title: '办理条件' }, { key: 'actions', title: '操作', align: 'right', width: '150px' }
]
export default {
  name: 'FundingPublicityView',
  components: { AppConfirmDialog, AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, DataTable, StatusTag: AppStatusTag, AppPagination },
  props: { ctx: { type: Object, default: null } },
  data() { return { publicityColumns: PUBLICITY_COLUMNS, loading: true, busy: false, loadSeq: 0, errorMessage: '', items: [], total: 0, page: 1, pageSize: 20, statusCounts: {}, batchId: '', projectId: '', scanResult: '', dialog: { visible: false, kind: '', row: null, batchId: '' } } },
  computed: {
    pageState() { return this.loading ? 'loading' : this.errorMessage ? 'error' : 'ready' },
    unfinishedCount() { return ['SUBMITTED', 'COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW', 'RETURNED'].reduce((n, key) => n + Number(this.statusCounts[key] || 0), 0) },
    grantedCount() { return Number(this.statusCounts.GRANTED || 0) }
  },
  mounted() { this.applyRouteContext(); this.load() },
  beforeUnmount() { this.loadSeq++ },
  watch: { '$route.query'(value, previous) {
    if (String(value?.batchId || '') !== String(previous?.batchId || '') || String(value?.projectId || '') !== String(previous?.projectId || '')) {
      this.applyRouteContext(); this.page = 1; this.scanResult = ''; this.dialog.visible = false; this.load()
    }
  } },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyRouteContext() { const q = this.$route.query || {}; this.batchId = String(q.batchId || '').trim(); this.projectId = String(q.projectId || '').trim() },
    backToFunding() { this.$router.push({ path: '/admin/student-affairs/funding', query: { ...(this.batchId ? { batchId: this.batchId } : {}), ...(this.projectId ? { projectId: this.projectId } : {}) } }) },
    goDisbursement() { if (this.batchId && this.grantedCount > 0) this.$router.push({ path: '/admin/student-affairs/funding/disbursements', query: { batchId: this.batchId, source: 'publicity', ...(this.projectId ? { projectId: this.projectId } : {}) } }) },
    goAppeals(row) { this.$router.push({ path: '/admin/student-affairs/funding/appeals', query: { applicationId: row.applicationId } }) },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', batchId: this.batchId || undefined, page: this.page, pageSize: this.pageSize })
        if (seq !== this.loadSeq) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '公示名单加载失败')
        this.items = res.data.items || []; this.total = Number(res.data.total || 0); this.statusCounts = res.data.statusCounts || {}
        const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize))
        if (this.page > lastPage) { this.page = lastPage; await this.load() }
      } catch (e) { if (seq === this.loadSeq) this.errorMessage = e.message || '公示名单加载失败' }
      finally { if (seq === this.loadSeq) this.loading = false }
    },
    openScan() { if (!this.busy && this.total > 0) this.dialog = { visible: true, kind: 'scan', batchId: this.batchId, row: null } },
    openConfirm(row) { if (!this.busy && row.allowedActions?.includes('PUBLICITY_CONFIRM')) this.dialog = { visible: true, kind: 'single', row: { ...row }, batchId: this.batchId } },
    async submitConfirmation() {
      if (this.busy || !this.dialog.visible) return
      const { kind, row, batchId } = this.dialog
      if (kind === 'single' && (!row?.allowedActions?.includes('PUBLICITY_CONFIRM') || row.version == null)) return
      this.busy = true
      try {
        const res = kind === 'scan' ? await studentAffairsApi.scanFundingPublicity(batchId || undefined) : await studentAffairsApi.confirmFundingPublicity(row.applicationId, row.version)
        if (res.code !== 0) throw new Error(res.message || '确认失败，请刷新核对')
        if (kind === 'scan') {
          const r = res.data || {}
          const reasons = [['尚未到期', r.notDue], ['申诉待复核', r.skippedAppeal], ['额度冲突', r.quotaConflict], ['资格变化', r.eligibilityConflict], ['批次失效', r.invalidBatch], ['公示时间缺失', r.invalidPublicity], ['状态变化或其他任务正在办理', r.stale]]
            .filter(([, count]) => Number(count) > 0).map(([label, count]) => `${label} ${Number(count)} 人`)
          this.scanResult = [`已确认 ${Number(r.count || 0)} 人`, ...reasons].join('；') + '。'
        } else toast.success('已确认获资助，可进入发放准备')
        this.dialog.visible = false; await this.load()
      } catch (e) { toast.error(e.message || '确认失败，请重试') }
      finally { this.busy = false }
    },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || '项目类型待确认' },
    amountText(a) { return a == null || a === '' ? '尚未确定' : typeof a === 'number' || /^\d+(\.\d+)?$/.test(a) ? `¥${Number(a).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}` : a },
    timeText(value) { if (!value) return '待核查'; const d = new Date(value); return Number.isNaN(d.getTime()) ? '待核查' : d.toLocaleString('zh-CN', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  }
}
</script>

<style scoped>
.fp-toolbar,.fp-tools,.fp-next { display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap }
.fp-toolbar { margin-bottom:16px }
.fp-total { margin-left:16px;color:var(--text-secondary);font-size:13px }
.fp-link { border:0;background:transparent;color:var(--color-primary);font:inherit;cursor:pointer;padding:8px;border-radius:8px }
.fp-link:disabled { opacity:.5;cursor:default }
.fp-link:focus-visible { outline:2px solid var(--color-primary);outline-offset:2px }
small { display:block;font-size:12px;color:var(--text-tertiary);margin-top:5px }
.fp-muted,.fp-next p,.fp-empty p { color:var(--text-secondary);font-size:13px;line-height:1.7 }
.fp-result { padding:14px 16px;margin-bottom:16px;border:1px solid var(--border-default);border-left:3px solid var(--color-primary);border-radius:12px;background:var(--bg-surface) }
.fp-result p { margin:6px 0;line-height:1.7 }.fp-result span { color:var(--text-secondary);font-size:12px }
.fp-next { margin-top:16px;padding:4px 16px }.fp-next strong { font-size:14px }.fp-next p { margin:6px 0 }
.fp-empty { text-align:center;padding:32px 16px }.fp-dialog-context { padding:14px;border:1px solid var(--border-default);border-radius:12px;margin-bottom:12px }
.fp-dialog-context p { line-height:1.7;margin:8px 0;color:var(--text-secondary) }
@media (max-width:640px) { .fp-toolbar>div,.fp-tools { width:100% }.fp-total { float:right }.fp-next { padding:8px 0 } }
</style>
