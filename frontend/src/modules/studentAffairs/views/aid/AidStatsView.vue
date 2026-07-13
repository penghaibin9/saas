<template>
  <AppPageShell
    title="困难认定统计"
    subtitle="按状态与核定等级聚合，仅统计口径，不含家庭经济明细。数据范围与认定台账一致。"
    role-name="学工处 / 资助老师"
    data-scope-name="按数据范围聚合"
    watermark-purpose="困难认定统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载认定统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <div class="ss-cols">
        <AppSectionCard title="按状态分布">
          <BreakdownTable :rows="stats.byStatus" :label-map="STATUS_LABELS" empty="暂无申请" />
        </AppSectionCard>
        <AppSectionCard title="按核定等级分布">
          <BreakdownTable :rows="stats.byLevel" :label-map="LEVEL_LABELS" empty="暂无等级数据" />
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import BreakdownTable from '@/modules/studentAffairs/views/common/BreakdownTable.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const STATUS_LABELS = { DRAFT: '草稿', SUBMITTED: '已提交', CLASS_REVIEW: '班级评议', COUNSELOR_REVIEW: '辅导员初审', COLLEGE_REVIEW: '学院复审', SCHOOL_REVIEW: '学校终审', PUBLICITY: '公示中', APPROVED: '已通过', REJECTED: '已驳回', ADJUST_REVIEW: '动态调整', ARCHIVED: '已归档' }
const LEVEL_LABELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }

export default {
  name: 'AidStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, BreakdownTable },
  data() { return { loading: true, errorMessage: '', stats: { total: 0, approved: 0, byStatus: [], byLevel: [] }, STATUS_LABELS, LEVEL_LABELS } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = (this.stats.total || 0) - (this.stats.approved || 0)
      return [
        { key: 't', label: '申请总数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'a', label: '已通过', value: this.stats.approved || 0, accent: 'success' },
        { key: 'p', label: '在途/未通过', value: pending, accent: pending ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getAidStats()
      if (res.code === 0 && res.data) {
        this.stats = res.data
      } else {
        this.errorMessage = res.message || '认定统计加载失败'
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ss-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .ss-cols { grid-template-columns: 1fr; } }
</style>
