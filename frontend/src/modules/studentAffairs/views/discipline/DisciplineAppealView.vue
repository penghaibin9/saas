<template>
  <AppPageShell
    title="处分送达与申诉"
    subtitle="已生效处分的决定书送达登记，及学生申诉的复核（维持/变更/撤销）。"
    role-name="学工处 / 学院"
    data-scope-name="学院本院 / 学工处全校"
    watermark-purpose="处分送达与申诉复核"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/discipline')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="已生效处分 · 送达 / 发起申诉">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>处分类型</th><th>送达</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="c in effectiveCases" :key="c.caseId">
              <td><strong>{{ c.realName || ('学生#' + c.studentId) }}</strong></td>
              <td>{{ discLabel(c.discType) }}</td>
              <td>{{ c.deliveredAt ? (deliveryLabel(c.deliveryMethod) + ' · ' + c.deliveredAt.slice(0,10)) : '未送达' }}</td>
              <td class="ap-ops">
                <AppPermissionButton v-if="!c.deliveredAt" code="studentAffairs.discipline.deliver" size="sm" :loading="acting===c.caseId" @click="deliver(c)">登记送达</AppPermissionButton>
                <AppPermissionButton code="studentAffairs.discipline.appeal.create" size="sm" variant="secondary" :loading="acting===c.caseId" @click="appeal(c)">发起申诉</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!effectiveCases.length"><td colspan="4" class="sa-empty">暂无已生效处分</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard title="申诉复核">
        <div class="ap-filters">
          <button v-for="f in appealFilters" :key="f.key" type="button" class="ap-chip"
                  :class="{ 'is-on': appealStatus === f.key }" @click="setAppealStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>申诉理由</th><th>状态</th><th>复核意见</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in appeals" :key="a.appealId">
              <td>{{ a.realName || ('学生#' + a.studentId) }}</td>
              <td class="ap-reason">{{ a.reason }}</td>
              <td><StatusTag :type="appealType(a.status)" :label="a.statusLabel || a.status" dot /></td>
              <td class="ap-opinion">{{ a.reviewOpinion || '—' }}</td>
              <td>
                <AppPermissionButton v-if="['SUBMITTED','REVIEWING'].includes(a.status)" code="studentAffairs.discipline.appeal.review" size="sm" :loading="acting===a.appealId" @click="review(a)">复核</AppPermissionButton>
                <span v-else class="ap-dash">—</span>
              </td>
            </tr>
            <tr v-if="!appeals.length"><td colspan="5" class="sa-empty">暂无申诉</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const DISC = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const DELIVERY = { DIRECT: '直接送达', MAIL: '邮寄', PUBLIC: '公告', LEAVE: '留置' }
const RESULT = { UPHELD: '维持原处分', REVISED: '变更处分', REVOKED: '撤销处分' }
const APPEAL_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' },
  { key: 'UPHELD', label: '已维持' }, { key: 'REVISED', label: '已变更' }, { key: 'REVOKED', label: '已撤销' }
]

export default {
  name: 'DisciplineAppealView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, acting: '', errorMessage: '', effectiveCases: [], appeals: [], appealStatus: '', appealFilters: APPEAL_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const undelivered = this.effectiveCases.filter((c) => !c.deliveredAt).length
      const pending = this.appeals.filter((a) => ['SUBMITTED', 'REVIEWING'].includes(a.status)).length
      return [
        { key: 'e', label: '已生效处分', value: this.effectiveCases.length, accent: 'primary' },
        { key: 'u', label: '待送达', value: undelivered, accent: undelivered ? 'warning' : 'success' },
        { key: 'p', label: '待复核申诉', value: pending, accent: pending ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [cs, ap] = await Promise.all([
        studentAffairsApi.getDisciplineCases({ status: 'EFFECTIVE', pageSize: 300 }),
        studentAffairsApi.getDisciplineAppeals({ status: this.appealStatus, pageSize: 300 })
      ])
      if (cs.code === 0 && cs.data) this.effectiveCases = cs.data.items || []
      else this.errorMessage = cs.message || '加载失败'
      this.appeals = (ap.code === 0 && ap.data) ? (ap.data.items || []) : []
      this.loading = false
    },
    setAppealStatus(k) { if (this.appealStatus === k) return; this.appealStatus = k; this.load() },
    async deliver(c) {
      const method = window.prompt('送达方式：DIRECT 直接 / MAIL 邮寄 / PUBLIC 公告 / LEAVE 留置', 'DIRECT')
      if (!method) return
      this.acting = c.caseId
      const res = await studentAffairsApi.deliverDiscipline(c.caseId, { method: method.trim().toUpperCase() })
      this.acting = ''
      if (res.code === 0) { toast.success('已登记送达'); this.load() } else toast.error(res.message || '送达失败')
    },
    async appeal(c) {
      const reason = window.prompt('申诉理由（至少5字）：')
      if (!reason) return
      this.acting = c.caseId
      const res = await studentAffairsApi.submitDisciplineAppeal(c.caseId, reason)
      this.acting = ''
      if (res.code === 0) { toast.success('申诉已提交'); this.load() } else toast.error(res.message || '申诉失败')
    },
    async review(a) {
      const result = window.prompt('复核结论：UPHELD 维持 / REVISED 变更 / REVOKED 撤销', 'UPHELD')
      if (!result) return
      const opinion = window.prompt('复核意见（至少5字）：')
      if (!opinion) return
      this.acting = a.appealId
      const res = await studentAffairsApi.reviewDisciplineAppeal(a.appealId, result.trim().toUpperCase(), opinion)
      this.acting = ''
      if (res.code === 0) { toast.success('已复核'); this.load() } else toast.error(res.message || '复核失败')
    },
    discLabel(t) { return DISC[t] || t },
    deliveryLabel(m) { return DELIVERY[m] || m },
    appealType(s) { return ({ SUBMITTED: 'warning', REVIEWING: 'processing', UPHELD: 'default', REVISED: 'success', REVOKED: 'success', WITHDRAWN: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ap-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ap-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ap-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ap-reason, .ap-opinion { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 260px; }
.ap-ops { display: flex; gap: 6px; }
.ap-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
