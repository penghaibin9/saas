<template>
  <AppPageShell
    title="活动与第二课堂统计"
    subtitle="活动数量、报名签到概览与第二课堂学分产出聚合。仅聚合口径，供团委/学工处掌握全局。"
    role-name="团委 / 学工处"
    data-scope-name="按数据范围聚合"
    watermark-purpose="活动二课统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载活动统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <BusinessMetrics class="compact-metrics" :items="metricCards" />

      <div class="as-cols">
        <AppSectionCard title="按活动类型分布">
          <p class="activity-stats-hint">了解活动、志愿服务、讲座、竞赛和社会实践的数量结构。</p>
          <DataTable v-if="byType.length" :columns="typeColumns" :rows="byType" row-key="key">
            <template #cell-label="{ row }">{{ typeLabel(row.key) }}</template>
            <template #cell-count="{ row }"><strong class="activity-stat-number">{{ row.count }}</strong></template>
          </DataTable>
          <p v-else class="sa-empty">当前范围暂无活动类型数据。</p>
        </AppSectionCard>

        <AppSectionCard title="按活动状态分布">
          <p class="activity-stats-hint">重点关注报名中、进行中和待确认活动，避免活动结束后名单长期未确认。</p>
          <DataTable v-if="byStatus.length" :columns="statusColumns" :rows="byStatus" row-key="key">
            <template #cell-label="{ row }">{{ statusLabel(row.key) }}</template>
            <template #cell-count="{ row }"><strong class="activity-stat-number">{{ row.count }}</strong></template>
          </DataTable>
          <p v-else class="sa-empty">当前范围暂无活动状态数据。</p>
        </AppSectionCard>
      </div>

      <AppSectionCard title="第二课堂产出（按类型）">
        <p class="activity-stats-hint">展示已确认活动产生的第二课堂学时、德育积分和志愿时长聚合，不替代学生个人成绩单。</p>
        <DataTable v-if="creditByType.length" :columns="creditColumns" :rows="creditByType" row-key="key">
          <template #cell-label="{ row }">{{ creditTypeLabel(row.key) }}</template>
          <template #cell-value="{ row }"><strong class="activity-credit-value">{{ row.value }}</strong></template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无已确认的第二课堂产出。</p>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import BusinessMetrics from '@/components/workspace/BusinessMetrics.vue'
import { AppGlobalState, AppPageShell, AppSectionCard } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE = { ACTIVITY: '活动', VOLUNTEER: '志愿服务', LECTURE: '讲座报告', COMPETITION: '竞赛', PRACTICE: '社会实践' }
const STATUS = { DRAFT: '草稿', PUBLISHED: '报名中', ENROLL_CLOSED: '报名截止', ONGOING: '进行中', FINISHED: '待确认', CONFIRMED: '已确认', CANCELLED: '已取消', ARCHIVED: '已归档' }
const CTYPE = { SECOND_CLASS: '第二课堂学时', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }
const TYPE_COLUMNS = [{ key: 'label', title: '类型' }, { key: 'count', title: '活动数' }]
const STATUS_COLUMNS = [{ key: 'label', title: '状态' }, { key: 'count', title: '活动数' }]
const CREDIT_COLUMNS = [{ key: 'label', title: '学分类型' }, { key: 'value', title: '合计' }]

export default {
  name: 'ActivityStatsView',
  components: { BusinessMetrics, AppGlobalState, AppPageShell, AppSectionCard, DataTable },
  data() { return { typeColumns: TYPE_COLUMNS, statusColumns: STATUS_COLUMNS, creditColumns: CREDIT_COLUMNS, loading: true, errorMessage: '', stats: {} } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    byType() { return this.stats.byType || [] },
    byStatus() { return this.stats.byStatus || [] },
    creditByType() { return this.stats.creditByType || [] },
    metricCards() {
      const s = this.stats
      return [
        { key: 'a', label: '活动总数', value: s.totalActivities || 0, accent: 'primary' },
        { key: 'e', label: '报名人次', value: s.totalSignups || 0, accent: 'primary' },
        { key: 'c', label: '签到人次', value: s.totalCheckins || 0, accent: 'success' },
        { key: 's', label: '获学分学生', value: s.creditStudents || 0, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getActivityStats()
      if (res.code === 0 && res.data) {
        this.stats = res.data
      } else {
        this.errorMessage = res.message || '活动统计加载失败'
      }
      this.loading = false
    },
    typeLabel(k) { return TYPE[k] || k || '未分类' },
    statusLabel(k) { return STATUS[k] || k || '—' },
    creditTypeLabel(k) { return CTYPE[k] || k || '—' }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.as-cols { min-width: 0; display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4); }
.activity-stats-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.activity-stat-number { color: var(--primary-700); font-size: var(--font-size-lg); font-variant-numeric: tabular-nums; }
.activity-credit-value { color: var(--success-700, #15803d); font-size: var(--font-size-lg); font-variant-numeric: tabular-nums; }
.as-cols > * { min-width: 0; }
.as-cols :deep(.dt__table) { min-width: 0; }
@media (max-width: 960px) { .as-cols { grid-template-columns: 1fr; } }
.compact-metrics { flex: 1; min-width: 0; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-md); margin-bottom: 16px; gap: 12px 24px; }
.compact-metrics :deep(> div) { display: flex; align-items: baseline; gap: 12px; min-width: 125px; }
.compact-metrics :deep(dd) { margin: 0; font-size: 24px; }
@media (max-width: 640px) { .compact-metrics { flex-basis: 100%; } }
</style>
