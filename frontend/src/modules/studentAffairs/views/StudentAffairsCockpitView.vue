<template>
  <AppPageShell
    title="学工统计驾驶舱"
    subtitle="学工各业务域统一概览；可用域展示真实指标，暂未形成独立口径的域明确标记为降级。"
    role-name="学工处 / 校领导"
    data-scope-name="按数据范围聚合"
    watermark-purpose="学工统计驾驶舱"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载驾驶舱..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="cp-grid">
        <div v-for="d in domains" :key="d.key" class="cp-cell" :class="{ 'is-error': d.status === 'ERROR' || d.status === 'DEGRADED' }">
          <AppMetricCard
            v-if="d.status === 'OK'"
            :title="d.label"
            :value="d.total"
            drillable
            :drill-target="d.route || ''"
            @drill="goRoute"
          />
          <div v-else class="cp-unavailable" @click="goRoute(d.route)">
            <div class="cp-unavailable__title">{{ d.label }}</div>
            <div class="cp-unavailable__msg">{{ d.message || '统计暂不可用' }}</div>
          </div>
          <div v-if="d.status === 'OK' && d.highlightLabel" class="cp-cell__hl">{{ d.highlightLabel }}：<b>{{ d.highlight }}</b></div>
          <div v-if="d.status === 'OK' && metricPreview(d).length" class="cp-cell__metrics">
            <span v-for="metric in metricPreview(d)" :key="metric.key">{{ metric.label }}：<b>{{ metric.value }}</b></span>
          </div>
        </div>
      </div>

      <AppSectionCard title="数据说明">
        <div v-if="reconcileOk !== null" class="cp-recon" :class="reconcileOk ? 'is-ok' : 'is-bad'">
          处分投影对账：<StatusTag :type="reconcileOk ? 'success' : 'danger'" :label="reconcileOk ? '一致' : '不一致（需核查）'" dot />
        </div>
        <div v-else class="cp-recon">处分投影对账：统计暂不可用</div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsCockpitView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() { return { loading: true, errorMessage: '', domains: [], reconcileOk: true } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.load() },
  methods: {
    metricPreview(domain) {
      return Object.entries(domain.metrics || {})
        .filter(([, value]) => typeof value === 'number' || typeof value === 'string')
        .filter(([key]) => !['total', 'totalActivities'].includes(key))
        .slice(0, 2)
        .map(([key, value]) => ({ key, label: this.metricLabel(key), value }))
    },
    metricLabel(key) {
      return {
        occupiedBeds: '已入住床位', vacantBeds: '空床位', pendingReview: '待审批',
        overdue: '逾期', highCritical: '高危/危急', open: '未关闭',
        completed: '已完成', openCrisis: '未关闭危机', granted: '已获资助',
        approved: '已认定', creditStudents: '获学分学生'
      }[key] || key
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getStatsCockpit()
      if (res.code === 0 && res.data) {
        this.domains = res.data.domains || []
        const rc = res.data.disciplineReconcileConsistent
        this.reconcileOk = rc === null || rc === undefined ? null : rc !== false
      } else {
        this.errorMessage = res.message || '驾驶舱加载失败'
      }
      this.loading = false
    },
    goRoute(route) { if (route) this.$router.push(route) }
  }
}
</script>

<style scoped>
.cp-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.cp-cell { display: flex; flex-direction: column; gap: var(--space-1); }
.cp-cell__hl { font-size: var(--font-size-sm); color: var(--text-secondary); padding: 0 var(--space-1); }
.cp-cell__hl b { color: var(--text-primary); }
.cp-cell__metrics { display: flex; flex-wrap: wrap; gap: var(--space-2); padding: 0 var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cp-cell__metrics b { color: var(--text-secondary); }
.cp-cell__err { font-size: var(--font-size-sm); color: var(--danger, #dc2626); padding: 0 var(--space-1); }
.cp-unavailable {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--border-color);
  background: var(--bg-secondary, #f8fafc);
  cursor: pointer;
  min-height: 88px;
}
.cp-unavailable__title { font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-2); }
.cp-unavailable__msg { font-size: var(--font-size-md); color: var(--warning, #b45309); font-weight: 600; }
.cp-recon { padding: var(--space-3); border-radius: var(--radius-md); }
.cp-recon.is-ok { background: rgba(34,197,94,0.08); }
.cp-recon.is-bad { background: rgba(239,68,68,0.08); }
@media (max-width: 960px) { .cp-grid { grid-template-columns: 1fr 1fr; } }
</style>
