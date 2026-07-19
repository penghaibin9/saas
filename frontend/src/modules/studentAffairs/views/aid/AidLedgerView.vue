<template>
  <AppPageShell
    title="困难认定台账"
    subtitle="全量认定申请只读台账，按状态 / 等级筛选。家庭经济明细在台账不呈现，需到工作台鉴权查看。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="困难认定台账查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载认定台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="认定申请记录">
        <div class="al-filters">
          <div class="al-fgroup">
            <button v-for="f in statusFilters" :key="f.key" type="button" class="al-chip"
                    :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
          </div>
          <div class="al-fgroup">
            <button v-for="f in levelFilters" :key="f.key" type="button" class="al-chip al-chip--lv"
                    :class="{ 'is-on': activeLevel === f.key }" @click="setLevel(f.key)">{{ f.label }}</button>
          </div>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>申请等级</th><th>核定等级</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="it in items" :key="it.applyId">
              <td><strong>{{ it.realName || ('学生#' + it.studentId) }}</strong></td>
              <td>{{ it.studentNo || '—' }}</td>
              <td>{{ levelLabel(it.applyLevel) }}</td>
              <td>{{ it.finalLevel ? levelLabel(it.finalLevel) : '—' }}</td>
              <td><StatusTag :type="statusType(it.status)" :label="it.statusLabel || it.status" dot /></td>
            </tr>
            <tr v-if="!items.length"><td colspan="5" class="sa-empty">当前范围与筛选下暂无认定申请</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const STATUS_FILTERS = [
  { key: '', label: '全部' },
  { key: 'CLASS_REVIEW', label: '班级评议' },
  { key: 'COLLEGE_REVIEW', label: '学院复审' },
  { key: 'SCHOOL_REVIEW', label: '学校终审' },
  { key: 'PUBLICITY', label: '公示中' },
  { key: 'APPROVED', label: '已通过' },
  { key: 'REJECTED', label: '已驳回' }
]
const LEVEL_FILTERS = [
  { key: '', label: '全部等级' },
  { key: 'SPECIAL', label: '特别困难' },
  { key: 'DIFFICULT', label: '困难' },
  { key: 'GENERAL', label: '一般困难' }
]

export default {
  name: 'AidLedgerView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, errorMessage: '', all: [], items: [], activeStatus: '', activeLevel: '', statusFilters: STATUS_FILTERS, levelFilters: LEVEL_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.all.filter((x) => x.status === k).length
      return [
        { key: 'all', label: '申请总数', value: this.all.length, accent: 'primary' },
        { key: 'ap', label: '已通过', value: s('APPROVED'), accent: 'success' },
        { key: 'pub', label: '公示中', value: s('PUBLICITY'), accent: 'warning' },
        { key: 'rj', label: '已驳回', value: s('REJECTED'), accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 注：后端 /aid/applications 支持真实 page/pageSize 分页，但本页状态/等级筛选是对
      // 已拉取全量数据做前端过滤（applyFilter），若改为真分页需把筛选参数一并发给后端、
      // 重新设计翻页与筛选联动逻辑，超出本次仅替换交互展示层的范围，故暂保留一次性拉取。
      const res = await studentAffairsApi.getAidApplications({ pageSize: 500 })
      if (res.code === 0 && res.data) {
        this.all = res.data.items || []
        this.applyFilter()
      } else {
        this.errorMessage = res.message || '认定台账加载失败'
      }
      this.loading = false
    },
    applyFilter() {
      this.items = this.all.filter((x) =>
        (!this.activeStatus || x.status === this.activeStatus) &&
        (!this.activeLevel || x.applyLevel === this.activeLevel || x.finalLevel === this.activeLevel))
    },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    setLevel(k) { this.activeLevel = k; this.applyFilter() },
    levelLabel(l) { return LEVELS[l] || l || '—' },
    statusType(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'PUBLICITY') return 'warning'
      if (['REGISTERED', 'DRAFT'].includes(s)) return 'default'
      return 'processing'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.al-filters { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-3); }
.al-fgroup { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.al-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.al-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.al-chip--lv.is-on { background: var(--warning-500, #d97706); border-color: var(--warning-500, #d97706); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
