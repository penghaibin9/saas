<template>
  <AppPageShell
    title="第二课堂积分申诉"
    subtitle="学生对二课学时缺记/记错提出申诉，审核通过后按主张补记学分（进二课台账）。"
    role-name="团委 / 学工处"
    data-scope-name="按数据范围（辅导员限本班）"
    watermark-purpose="第二课堂积分申诉"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载申诉..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.activity.create" :loading="saving" @click="openForm">代录申诉</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="提交积分申诉">
        <div class="ca-grid">
          <label class="ca-field"><span>学生主档ID *</span><input v-model.number="form.studentId" type="number" class="ca-input" /></label>
          <label class="ca-field"><span>类型</span>
            <select v-model="form.appealType" class="ca-input"><option value="MISSING">缺记</option><option value="WRONG">记错</option></select></label>
          <label class="ca-field"><span>学分类型</span>
            <select v-model="form.claimCreditType" class="ca-input"><option value="SECOND_CLASS">二课学时</option><option value="MORAL">德育积分</option><option value="VOLUNTEER_HOUR">志愿时长</option></select></label>
          <label class="ca-field"><span>主张数值 *</span><input v-model.number="form.claimValue" type="number" min="0" step="0.5" class="ca-input" /></label>
          <label class="ca-field ca-field--wide"><span>申诉理由 *（≥5字）</span><input v-model.trim="form.reason" class="ca-input" /></label>
        </div>
        <p v-if="form.error" class="ca-error">{{ form.error }}</p>
        <div class="ca-actions">
          <button type="button" class="ca-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.activity.create" :loading="saving" @click="save">提交</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="申诉记录">
        <div class="ca-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="ca-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>类型</th><th>主张</th><th>理由</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in items" :key="a.appealId">
              <td><strong>{{ a.realName || ('学生#' + a.studentId) }}</strong></td>
              <td>{{ a.appealType === 'MISSING' ? '缺记' : '记错' }}</td>
              <td>{{ ctypeLabel(a.claimCreditType) }} {{ a.claimValue != null ? a.claimValue : '—' }}</td>
              <td class="ca-reason">{{ a.reason }}</td>
              <td><StatusTag :type="statusType(a.status)" :label="a.statusLabel || a.status" dot />
                <em v-if="a.reviewOpinion" class="ca-opinion">{{ a.reviewOpinion }}</em></td>
              <td class="ca-ops">
                <template v-if="a.status === 'SUBMITTED'">
                  <AppPermissionButton code="studentAffairs.activity.confirm" size="sm" :loading="acting===a.appealId" @click="review(a,'APPROVE')">通过</AppPermissionButton>
                  <AppPermissionButton code="studentAffairs.activity.confirm" size="sm" variant="secondary" danger :loading="acting===a.appealId" @click="review(a,'REJECT')">驳回</AppPermissionButton>
                </template>
                <span v-else class="ca-dash">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无积分申诉</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 驳回意见：不挂快捷用语——现有词库无「二课积分申诉驳回」口径，
         sa.aid.reject 是资助、common.reject 是违纪立案，套过来都不对。 -->
    <AppConfirmDialog
      v-model:visible="rejDlg.visible" title="驳回积分申诉" type="danger" confirm-text="确认驳回"
      require-reason :reason-min-length="5" reason-label="驳回意见（≥5 字）"
      :submitting="acting === rejDlg.appealId" @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const CTYPE = { SECOND_CLASS: '二课学时', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待审核' },
  { key: 'APPROVED', label: '已通过' }, { key: 'REJECTED', label: '已驳回' }
]

export default {
  name: 'CreditAppealView',
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
    StatusTag: AppStatusTag
  },
  data() {
    return {
      loading: true, saving: false, acting: '', errorMessage: '', all: [], items: [],
      activeStatus: '', statusFilters: STATUS_FILTERS,
      formVisible: false, form: this.blankForm(),
      rejDlg: { visible: false, appealId: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.all.filter((a) => a.status === k).length
      return [
        { key: 'p', label: '待审核', value: s('SUBMITTED'), accent: 'warning' },
        { key: 'a', label: '已通过补记', value: s('APPROVED'), accent: 'success' },
        { key: 'r', label: '已驳回', value: s('REJECTED'), accent: 'default' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    blankForm() { return { studentId: null, appealType: 'MISSING', claimCreditType: 'SECOND_CLASS', claimValue: null, reason: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getCreditAppeals({ pageSize: 300 })
      if (res.code === 0 && res.data) { this.all = res.data.items || []; this.applyFilter() }
      else this.errorMessage = res.message || '申诉加载失败'
      this.loading = false
    },
    applyFilter() { this.items = this.activeStatus ? this.all.filter((a) => a.status === this.activeStatus) : this.all },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    openForm() { this.form = this.blankForm(); this.formVisible = true },
    async save() {
      const m = this.form
      if (!m.studentId || !m.reason || m.reason.length < 5 || !m.claimValue) { m.error = '学生ID、主张数值、理由(≥5字)必填'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.submitCreditAppeal({
        studentId: Number(m.studentId), appealType: m.appealType, claimCreditType: m.claimCreditType,
        claimValue: Number(m.claimValue), reason: m.reason
      })
      this.saving = false
      if (res.code === 0) { toast.success('申诉已提交'); this.formVisible = false; this.load() } else m.error = res.message || '提交失败'
    },
    async review(a, action) {
      if (action === 'REJECT') { this.rejDlg = { visible: true, appealId: a.appealId }; return }
      this.acting = a.appealId
      const res = await studentAffairsApi.reviewCreditAppeal(a.appealId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('已通过并补记'); this.load() } else toast.error(res.message || '审核失败')
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      this.acting = d.appealId
      const res = await studentAffairsApi.reviewCreditAppeal(d.appealId, 'REJECT', reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已驳回'); this.load() } else toast.error(res.message || '审核失败')
    },
    ctypeLabel(t) { return CTYPE[t] || t },
    statusType(s) { return ({ SUBMITTED: 'warning', APPROVED: 'success', REJECTED: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.ca-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.ca-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.ca-field--wide { grid-column: span 4; }
.ca-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ca-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.ca-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.ca-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.ca-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ca-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ca-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ca-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 220px; }
.ca-opinion { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.ca-ops { display: flex; gap: 6px; }
.ca-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .ca-grid { grid-template-columns: 1fr; } .ca-field--wide { grid-column: span 1; } }
</style>
