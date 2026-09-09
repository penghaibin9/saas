<template>
  <AppPageShell
    title="奖助申诉复核"
    watermark-purpose="资助公示申诉复核"
  >
    <template #actions>
      <button v-if="focusId || filterApplicationId" class="ob-chip" @click="clearFocus">查看全部申诉</button>
      <button class="ob-chip" :disabled="!!acting" @click="load">刷新</button>
    </template>
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">

      <details v-if="!focusId && !filterApplicationId" class="ob-intake"><summary>登记公示申诉 <span>{{ publicityPage.total }} 条公示申请</span></summary>
      <AppSectionCard title="公示中申请 · 可提申诉">
        <DataTable v-if="publicity.length" :columns="publicityColumns" :rows="publicity" row-key="applicationId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-projectType="{ row }">{{ typeLabel(row.projectType) }}</template>
          <template #cell-pending="{ row }">
            <StatusTag v-if="row.hasPendingAppeal" type="warning" label="申诉待复核" dot />
            <span v-else class="ob-dash">—</span>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.funding.view')" v-if="!row.hasPendingAppeal" code="studentAffairs.funding.view" size="sm" variant="secondary"
                                 :loading="acting===row.applicationId" @click="openAppeal(row)">提申诉</AppPermissionButton>
            <span v-else class="ob-dash">待复核</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的申请</p>
        <AppPagination v-model:page="publicityPage.page" v-model:pageSize="publicityPage.pageSize" :total="publicityPage.total" @change="load" />
      </AppSectionCard>
      </details>

      <AppSectionCard title="申诉复核">
        <div v-if="!focusId" class="ob-filters" aria-label="申诉状态">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="ob-chip"
                  :aria-pressed="appealStatus === f.key" :class="{ 'is-on': appealStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button><span class="ob-total">{{ appealPage.total }} 件</span>
        </div>
        <DataTable v-if="appeals.length" :columns="appealColumns" :rows="appeals" row-key="appealId">
          <template #cell-student="{ row }"><strong>{{ row.realName || ('学生#' + row.studentId) }}</strong><span class="ob-opinion">{{ row.studentNo }} · 申请 #{{ row.applicationId }}</span></template>
          <template #cell-appellant="{ row }">{{ row.appellantName || '匿名' }}</template>
          <template #cell-reason="{ row }"><span class="ob-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }">
            <StatusTag :type="appealType(row)" :label="row.status === 'CLOSED' ? (row.resultLabel || '已复核') : (row.statusLabel || row.status)" dot />
            <em v-if="row.reviewOpinion" class="ob-opinion">{{ row.reviewOpinion }}</em>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage') && row.allowedActions?.includes('REVIEW')" v-if="row.status === 'SUBMITTED'" code="studentAffairs.funding.publicity.manage" size="sm"
                                 :loading="acting===row.appealId" @click="openReview(row)">复核</AppPermissionButton>
            <span v-else class="ob-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">{{ focusId ? '该申诉不存在或超出当前范围，请返回全部申诉。' : '当前筛选下没有申诉' }}</p>
        <AppPagination v-if="!focusId" v-model:page="appealPage.page" v-model:pageSize="appealPage.pageSize" :total="appealPage.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="appealDlg.visible" :title="`对公示提出申诉 · ${appealDlg.who}`" type="warning"
      confirm-text="提交申诉" require-reason :reason-min-length="5" reason-label="申诉理由（≥5 字）"
      description="申诉将进入复核流程；成立则驳回资助申请，不成立则维持公示结果。"
      :submitting="acting === appealDlg.applicationId" @confirm="submitAppeal"
    >
      <AppFormItem label="申诉人">
        <AppTextInput v-model="appealDlg.appellantName" placeholder="可空；留空按匿名处理" />
      </AppFormItem>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="revDlg.visible" :title="`复核申诉 · ${revDlg.who || ''}`" type="primary"
      confirm-text="提交复核" require-reason :reason-min-length="5" reason-label="复核意见（≥5 字）"
      :submitting="acting === revDlg.appealId" @confirm="submitReview"
    >
      <div class="ob-review-context"><strong>申请 #{{ revDlg.applicationId }}</strong><p>{{ revDlg.reason }}</p></div>
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="APPEAL_RESULTS" />
      </AppFormItem>
      <p class="ob-impact">{{ revDlg.result === 'SUSTAINED' ? '申诉成立将驳回原资助申请，请确认事实与复核意见一致。' : revDlg.result === 'OVERRULED' ? '维持原公示；仍需公示期满后由学校确认获资助。' : '请选择核查后的结论，不会自动代选。' }}</p>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppTextInput, AppPagination
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const APPEAL_RESULTS = [
  { value: 'OVERRULED', label: '不成立 —— 维持公示获资助资格' },
  { value: 'SUSTAINED', label: '成立 —— 驳回资助申请' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' }, { key: 'CLOSED', label: '已复核' }
]
const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'projectType', title: '项目类型' },
  { key: 'pending', title: '申诉状态' },
  { key: 'actions', title: '操作', align: 'right', width: '120px' }
]
const APPEAL_COLUMNS = [
  { key: 'student', title: '被申诉学生' },
  { key: 'appellant', title: '申诉人' },
  { key: 'reason', title: '申诉理由' },
  { key: 'status', title: '状态/结论' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]

export default {
  name: 'FundingAppealView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppTextInput, AppPagination, StatusTag: AppStatusTag, DataTable
  },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      appealColumns: APPEAL_COLUMNS,
      loading: true, acting: '', errorMessage: '', publicity: [], appeals: [], appealStatus: 'SUBMITTED', statusFilters: STATUS_FILTERS,
      loadSeq: 0, focusId: '', filterApplicationId: '', publicityPage: { page: 1, pageSize: 20, total: 0 }, appealPage: { page: 1, pageSize: 20, total: 0 },
      appealDlg: { visible: false, applicationId: '', who: '', appellantName: '' },
      revDlg: { visible: false, appealId: '', result: 'OVERRULED' }
    }
  },
  computed: {
    APPEAL_RESULTS: () => APPEAL_RESULTS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.applyRoute(); this.load() },
  watch: { '$route.query'() { this.applyRoute(); this.appealPage.page = 1; this.load() } },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyRoute() { this.focusId = /^\d+$/.test(String(this.$route.query.recordId || '')) ? String(this.$route.query.recordId) : ''; this.filterApplicationId = /^\d+$/.test(String(this.$route.query.applicationId || '')) ? String(this.$route.query.applicationId) : '' },
    clearFocus() { const query = { ...this.$route.query }; delete query.recordId; delete query.applicationId; this.$router.replace({ query }) },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.errorMessage = ''
      const [pu, ap] = await Promise.all([
        (this.focusId || this.filterApplicationId) ? Promise.resolve({ code: 0, data: { items: [], total: 0 } }) : studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', page: this.publicityPage.page, pageSize: this.publicityPage.pageSize }),
        studentAffairsApi.getFundingAppeals({ status: this.focusId ? '' : this.appealStatus, appealId: this.focusId || undefined, applicationId: this.filterApplicationId || undefined, page: this.focusId ? 1 : this.appealPage.page, pageSize: this.appealPage.pageSize })
      ])
      if (seq !== this.loadSeq) return
      if (pu.code === 0 && pu.data) { this.publicity = pu.data.items || []; this.publicityPage.total = pu.data.total || 0 }
      else this.errorMessage = pu.message || '公示申请加载失败'
      if (ap.code === 0 && ap.data) { this.appeals = ap.data.items || []; this.appealPage.total = ap.data.total || 0 }
      else { this.appeals = []; this.errorMessage = ap.message || '申诉加载失败，请重试' }
      this.loading = false
    },
    setStatus(k) { if (this.appealStatus === k) return; this.appealStatus = k; this.appealPage.page = 1; this.load() },
    openAppeal(a) {
      this.appealDlg = { visible: true, applicationId: a.applicationId, who: a.realName || a.studentNo || '该生', appellantName: '' }
    },
    async submitAppeal({ reason }) {
      if (this.acting) return
      const d = this.appealDlg
      this.acting = d.applicationId
      const res = await studentAffairsApi.submitFundingAppeal(d.applicationId, {
        reason: reason.trim(), appellantName: d.appellantName.trim() || undefined
      })
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('申诉已提交'); this.load() } else toast.error(res.message || '提交失败')
    },
    openReview(o) {
      if (!o.allowedActions?.includes('REVIEW') || o.version == null) return
      this.revDlg = { visible: true, appealId: o.appealId, applicationId: o.applicationId, who: o.realName || o.studentNo, reason: o.reason, result: '', version: o.version }
    },
    async submitReview({ reason }) {
      if (this.acting) return
      const d = this.revDlg
      if (!['SUSTAINED', 'OVERRULED'].includes(d.result)) { toast.error('请选择复核结论'); return }
      this.acting = d.appealId
      const res = await studentAffairsApi.reviewFundingAppeal(d.appealId, d.result, reason.trim(), d.version)
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已复核'); this.load() } else toast.error(res.message || '复核失败，请刷新核对后重试')
    },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || (t ? '类型待确认' : '') },
    appealType(o) {
      if (o.status !== 'CLOSED') return 'warning'
      return o.result === 'SUSTAINED' ? 'danger' : 'success'
    }
  }
}
</script>

<style scoped>
.ob-intake { margin-bottom:16px; border:1px solid var(--border-light); border-radius:12px; background:var(--bg-card); }
.ob-intake summary { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; cursor:pointer; font-weight:600; }
.ob-intake summary span,.ob-total { color:var(--text-tertiary); font-size:12px; font-weight:400; }
.ob-total { margin-left:auto; align-self:center; }
.ob-review-context { padding:14px; background:var(--bg-page); border:1px solid var(--border-light); border-radius:10px; margin-bottom:16px; }
.ob-review-context p,.ob-reason { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; }
.ob-impact { font-size:13px; color:var(--text-secondary); padding:12px 0; line-height:1.6; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ob-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ob-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ob-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ob-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 240px; }
.ob-opinion { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.ob-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
