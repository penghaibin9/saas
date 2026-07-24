<template>
  <AppPageShell
    title="资助公示申诉复核"
    subtitle="公示期内对资助结果提出申诉并复核（成立则驳回申请 / 不成立则维持）。有进行中申诉的申请不可确认获资助。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="资助公示申诉复核"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

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
      </AppSectionCard>

      <AppSectionCard title="申诉复核">
        <div class="ob-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="ob-chip"
                  :class="{ 'is-on': appealStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <DataTable v-if="appeals.length" :columns="appealColumns" :rows="appeals" row-key="appealId">
          <template #cell-student="{ row }">{{ row.realName || ('学生#' + row.studentId) }}</template>
          <template #cell-appellant="{ row }">{{ row.appellantName || '匿名' }}</template>
          <template #cell-reason="{ row }"><span class="ob-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }">
            <StatusTag :type="appealType(row)" :label="row.status === 'CLOSED' ? (row.resultLabel || '已复核') : (row.statusLabel || row.status)" dot />
            <em v-if="row.reviewOpinion" class="ob-opinion">{{ row.reviewOpinion }}</em>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" v-if="row.status === 'SUBMITTED'" code="studentAffairs.funding.publicity.manage" size="sm"
                                 :loading="acting===row.appealId" @click="openReview(row)">复核</AppPermissionButton>
            <span v-else class="ob-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无申诉</p>
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
      v-model:visible="revDlg.visible" title="复核申诉" type="primary"
      confirm-text="提交复核" require-reason :reason-min-length="5" reason-label="复核意见（≥5 字）"
      :submitting="acting === revDlg.appealId" @confirm="submitReview"
    >
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="APPEAL_RESULTS" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppTextInput
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
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag, DataTable
  },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      appealColumns: APPEAL_COLUMNS,
      loading: true, acting: '', errorMessage: '', publicity: [], appeals: [], appealStatus: '', statusFilters: STATUS_FILTERS,
      appealDlg: { visible: false, applicationId: '', who: '', appellantName: '' },
      revDlg: { visible: false, appealId: '', result: 'OVERRULED' }
    }
  },
  computed: {
    APPEAL_RESULTS: () => APPEAL_RESULTS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.appeals.filter((o) => o.status === 'SUBMITTED').length
      const sustained = this.appeals.filter((o) => o.result === 'SUSTAINED').length
      return [
        { key: 'p', label: '公示中申请', value: this.publicity.length, accent: 'primary' },
        { key: 'w', label: '待复核申诉', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 's', label: '申诉成立(已驳回)', value: sustained, accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [pu, ap] = await Promise.all([
        studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', pageSize: 300 }),
        studentAffairsApi.getFundingAppeals({ status: this.appealStatus, pageSize: 300 })
      ])
      if (pu.code === 0 && pu.data) this.publicity = pu.data.items || []
      else this.errorMessage = pu.message || '加载失败'
      this.appeals = (ap.code === 0 && ap.data) ? (ap.data.items || []) : []
      this.loading = false
    },
    setStatus(k) { if (this.appealStatus === k) return; this.appealStatus = k; this.load() },
    openAppeal(a) {
      this.appealDlg = { visible: true, applicationId: a.applicationId, who: a.realName || a.studentNo || '该生', appellantName: '' }
    },
    async submitAppeal({ reason }) {
      const d = this.appealDlg
      this.acting = d.applicationId
      const res = await studentAffairsApi.submitFundingAppeal(d.applicationId, {
        reason: reason.trim(), appellantName: d.appellantName.trim() || undefined
      })
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('申诉已提交'); this.load() } else toast.error(res.message || '提交失败')
    },
    openReview(o) {
      this.revDlg = { visible: true, appealId: o.appealId, result: 'OVERRULED' }
    },
    async submitReview({ reason }) {
      const d = this.revDlg
      this.acting = d.appealId
      const res = await studentAffairsApi.reviewFundingAppeal(d.appealId, d.result, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已复核'); this.load() } else toast.error(res.message || '复核失败')
    },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t || '' },
    appealType(o) {
      if (o.status !== 'CLOSED') return 'warning'
      return o.result === 'SUSTAINED' ? 'danger' : 'success'
    }
  }
}
</script>

<style scoped>
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
