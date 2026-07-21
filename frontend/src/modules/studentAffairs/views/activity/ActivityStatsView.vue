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
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <div class="as-cols">
        <AppSectionCard title="按活动类型">
          <DataTable v-if="byType.length" :columns="typeColumns" :rows="byType" row-key="key">
            <template #cell-label="{ row }">{{ typeLabel(row.key) }}</template>
            <template #cell-count="{ row }">{{ row.count }}</template>
          </DataTable>
          <p v-else class="sa-empty">暂无数据</p>
        </AppSectionCard>

        <AppSectionCard title="按活动状态">
          <DataTable v-if="byStatus.length" :columns="statusColumns" :rows="byStatus" row-key="key">
            <template #cell-label="{ row }">{{ statusLabel(row.key) }}</template>
            <template #cell-count="{ row }">{{ row.count }}</template>
          </DataTable>
          <p v-else class="sa-empty">暂无数据</p>
        </AppSectionCard>
      </div>

      <AppSectionCard title="第二课堂学分产出（按类型）">
        <DataTable v-if="creditByType.length" :columns="creditColumns" :rows="creditByType" row-key="key">
          <template #cell-label="{ row }">{{ creditTypeLabel(row.key) }}</template>
          <template #cell-value="{ row }">{{ row.value }}</template>
        </DataTable>
        <p v-else class="sa-empty">暂无学分产出</p>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
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
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, DataTable },
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
        { key: 'e', label: '报名人次', value: s.totalSignups || 0, accent: 'info' },
        { key: 'c', label: '签到人次', value: s.totalCheckins || 0, accent: 'success' },
        { key: 's', label: '获学分学生', value: s.creditStudents || 0, accent: 'warning' }
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
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.as-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .as-cols { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
