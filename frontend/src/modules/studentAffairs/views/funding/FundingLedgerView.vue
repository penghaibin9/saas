<template>
  <AppPageShell
    title="资助发放台账"
    subtitle="全量资助申请只读台账，按项目类型 / 状态筛选。金额按当前角色脱敏由后端裁定。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="资助台账查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载资助台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="资助申请记录">
        <div class="fl-filters">
          <div class="fl-fgroup">
            <button v-for="f in typeFilters" :key="f.key" type="button" class="fl-chip"
                    :class="{ 'is-on': activeType === f.key }" @click="setType(f.key)">{{ f.label }}</button>
          </div>
          <div class="fl-fgroup">
            <button v-for="f in statusFilters" :key="f.key" type="button" class="fl-chip fl-chip--st"
                    :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
          </div>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>项目类型</th><th>来源</th><th>金额</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="it in items" :key="it.applicationId">
              <td><strong>{{ it.realName || ('学生#' + it.studentId) }}</strong></td>
              <td>{{ it.studentNo || '—' }}</td>
              <td>{{ typeLabel(it.projectType) }}</td>
              <td>{{ sourceLabel(it.applySource) }}</td>
              <td>{{ amountText(it.amount) }}</td>
              <td><StatusTag :type="statusType(it.status)" :label="it.statusLabel || it.status" dot /></td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">当前范围与筛选下暂无资助申请</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE_FILTERS = [
  { key: '', label: '全部类型' },
  { key: 'SCHOLARSHIP', label: '奖学金' },
  { key: 'GRANT', label: '助学金' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部状态' },
  { key: 'COUNSELOR_REVIEW', label: '辅导员初审' },
  { key: 'COLLEGE_REVIEW', label: '学院复审' },
  { key: 'PUBLICITY', label: '公示中' },
  { key: 'GRANTED', label: '已获资助' },
  { key: 'REJECTED', label: '已驳回' }
]

export default {
  name: 'FundingLedgerView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, errorMessage: '', all: [], items: [], activeType: '', activeStatus: '', typeFilters: TYPE_FILTERS, statusFilters: STATUS_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.all.filter((x) => x.status === k).length
      return [
        { key: 'all', label: '申请总数', value: this.all.length, accent: 'primary' },
        { key: 'gr', label: '已获资助', value: s('GRANTED'), accent: 'success' },
        { key: 'pub', label: '公示中', value: s('PUBLICITY'), accent: 'warning' },
        { key: 'rj', label: '已驳回', value: s('REJECTED'), accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFundingApplications({ pageSize: 500 })
      if (res.code === 0 && res.data) {
        this.all = res.data.items || []
        this.applyFilter()
      } else {
        this.errorMessage = res.message || '资助台账加载失败'
      }
      this.loading = false
    },
    applyFilter() {
      this.items = this.all.filter((x) =>
        (!this.activeType || x.projectType === this.activeType) &&
        (!this.activeStatus || x.status === this.activeStatus))
    },
    setType(k) { this.activeType = k; this.applyFilter() },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t || '—' },
    sourceLabel(s) { return ({ SELF: '自主申请', RECOMMEND: '推荐' })[s] || s || '—' },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) },
    statusType(s) {
      if (s === 'GRANTED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'PUBLICITY') return 'warning'
      if (['DRAFT', 'CANCELLED'].includes(s)) return 'default'
      return 'processing'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.fl-filters { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-3); }
.fl-fgroup { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.fl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
