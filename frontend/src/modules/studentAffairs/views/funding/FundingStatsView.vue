<template>
  <AppPageShell
    title="奖助统计"
    subtitle="按状态与项目类型聚合，计数口径不含金额明细（规避金额脱敏）。数据范围与资助台账一致。"
    role-name="学工处 / 资助老师"
    data-scope-name="按数据范围聚合"
    watermark-purpose="奖助统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载奖助统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <div class="ss-cols">
        <AppSectionCard title="按状态分布">
          <BreakdownTable :rows="stats.byStatus" :label-map="STATUS_LABELS" empty="暂无申请" />
        </AppSectionCard>
        <AppSectionCard title="按项目类型分布">
          <BreakdownTable :rows="stats.byType" :label-map="TYPE_LABELS" empty="暂无类型数据" />
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import BreakdownTable from '@/modules/studentAffairs/views/common/BreakdownTable.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const STATUS_LABELS = { DRAFT: '草稿', SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员初审', COLLEGE_REVIEW: '学院复审', SCHOOL_REVIEW: '学校终审', PUBLICITY: '公示中', GRANTED: '已获资助', REJECTED: '已驳回', RETURNED: '已退回', CANCELLED: '已取消', ARCHIVED: '已归档' }
const TYPE_LABELS = { SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助', GREEN_CHANNEL: '绿色通道' }

export default {
  name: 'FundingStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, BreakdownTable },
  data() { return { loading: true, errorMessage: '', stats: { total: 0, granted: 0, byStatus: [], byType: [] }, STATUS_LABELS, TYPE_LABELS } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = (this.stats.total || 0) - (this.stats.granted || 0)
      return [
        { key: 't', label: '申请总数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'g', label: '已获资助', value: this.stats.granted || 0, accent: 'success' },
        { key: 'p', label: '在途/未获', value: pending, accent: pending ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFundingStats()
      if (res.code === 0 && res.data) {
        this.stats = res.data
      } else {
        this.errorMessage = res.message || '奖助统计加载失败'
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
