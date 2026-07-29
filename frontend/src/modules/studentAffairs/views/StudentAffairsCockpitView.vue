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
      <section class="sa-summary-strip cockpit-summary" :class="{ 'has-warning': domains.some((d) => d.status !== 'OK') || reconcileOk === false }">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">统计健康状态</span>
          <h2 class="sa-summary-strip__title">
            已加载 {{ domains.length }} 个业务域，{{ domains.filter((d) => d.status === 'OK').length }} 个口径可用，{{ domains.filter((d) => d.status !== 'OK').length }} 个需关注
          </h2>
          <p class="sa-summary-strip__text">
            先处理统计不可用或数据对账不一致的业务域，再依据真实指标下钻。所有数字均按当前角色数据范围聚合，不使用浏览器单页数据二次拼算。
          </p>
        </div>
        <div class="cockpit-summary__status">
          <span>处分投影对账</span>
          <StatusTag v-if="reconcileOk !== null" :type="reconcileOk ? 'success' : 'danger'" :label="reconcileOk ? '一致' : '需核查'" dot />
          <span v-else class="cockpit-summary__unknown">暂不可用</span>
        </div>
      </section>

      <div class="cockpit-legend" aria-label="驾驶舱说明">
        <span><i class="is-ok"></i>真实统计可用，可点击下钻</span>
        <span><i class="is-warning"></i>统计降级或错误，显示原因而不显示假数字</span>
      </div>

      <div class="cp-grid">
        <div v-for="d in domains" :key="d.key" class="cp-cell" :class="{ 'is-error': d.status === 'ERROR' || d.status === 'DEGRADED' }">
          <div class="cp-cell__head">
            <span class="cp-cell__status" :class="d.status === 'OK' ? 'is-ok' : 'is-warning'">{{ d.status === 'OK' ? '口径正常' : '需要关注' }}</span>
          </div>
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
            <div v-if="d.route" class="cp-unavailable__link">进入业务页核查 →</div>
          </div>
          <div v-if="d.status === 'OK' && d.highlightLabel" class="cp-cell__hl">{{ d.highlightLabel }}：<b>{{ d.highlight }}</b></div>
          <div v-if="d.status === 'OK' && metricPreview(d).length" class="cp-cell__metrics">
            <span v-for="metric in metricPreview(d)" :key="metric.key">{{ metric.label }}：<b>{{ metric.value }}</b></span>
          </div>
        </div>
      </div>

      <AppSectionCard title="数据质量与使用说明">
        <div class="cp-quality-grid">
          <div class="cp-quality-item">
            <span>处分投影对账</span>
            <div v-if="reconcileOk !== null" class="cp-recon" :class="reconcileOk ? 'is-ok' : 'is-bad'">
              <StatusTag :type="reconcileOk ? 'success' : 'danger'" :label="reconcileOk ? '一致' : '不一致（需核查）'" dot />
            </div>
            <div v-else class="cp-recon">统计暂不可用</div>
          </div>
          <div class="cp-quality-item">
            <span>统计口径</span>
            <strong>当前角色数据范围</strong>
            <p>降级或错误域只显示原因，不把接口错误解释成 0。</p>
          </div>
          <div class="cp-quality-item">
            <span>建议动作</span>
            <strong>{{ domains.some((d) => d.status !== 'OK') || reconcileOk === false ? '优先核查异常域' : '可按业务需要下钻' }}</strong>
            <p>点击正常业务域可进入对应页面查看明细和处理待办。</p>
          </div>
        </div>
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
.cockpit-summary.has-warning { border-color: var(--warning-300, #fcd34d); background: var(--warning-50, #fffbeb); }
.cockpit-summary__status { display: grid; justify-items: end; gap: 5px; min-width: 120px; }
.cockpit-summary__status > span:first-child { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cockpit-summary__unknown { color: var(--warning-700); font-weight: 600; }
.cockpit-legend { display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-3); color: var(--text-secondary); font-size: var(--font-size-xs); }
.cockpit-legend span { display: inline-flex; align-items: center; gap: 6px; }
.cockpit-legend i { width: 8px; height: 8px; border-radius: 50%; }
.cockpit-legend i.is-ok { background: var(--success-500, #22c55e); }
.cockpit-legend i.is-warning { background: var(--warning-500, #f59e0b); }
.cp-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.cp-cell { position: relative; display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; padding: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-lg); background: var(--bg-card); }
.cp-cell.is-error { border-color: var(--warning-200, #fde68a); background: var(--warning-50, #fffbeb); }
.cp-cell__head { display: flex; justify-content: flex-end; min-height: 20px; }
.cp-cell__status { padding: 2px 7px; border-radius: var(--radius-full); font-size: 11px; }
.cp-cell__status.is-ok { background: var(--success-50, #f0fdf4); color: var(--success-700, #15803d); }
.cp-cell__status.is-warning { background: var(--warning-100, #fef3c7); color: var(--warning-800, #92400e); }
.cp-cell__hl { font-size: var(--font-size-sm); color: var(--text-secondary); padding: 0 var(--space-1); }
.cp-cell__hl b { color: var(--text-primary); }
.cp-cell__metrics { display: flex; flex-wrap: wrap; gap: var(--space-2); padding: 0 var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cp-cell__metrics b { color: var(--text-secondary); }
.cp-unavailable { padding: var(--space-4); border-radius: var(--radius-md); border: 1px dashed var(--warning-300, #fcd34d); background: rgba(255,255,255,.72); cursor: pointer; min-height: 108px; }
.cp-unavailable__title { font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-2); }
.cp-unavailable__msg { font-size: var(--font-size-md); color: var(--warning-800, #92400e); font-weight: 600; line-height: 1.5; }
.cp-unavailable__link { margin-top: var(--space-3); color: var(--primary-700); font-size: var(--font-size-xs); }
.cp-quality-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.cp-quality-item { padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-section); }
.cp-quality-item > span { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cp-quality-item > strong { display: block; margin-top: 5px; color: var(--text-primary); }
.cp-quality-item p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.55; }
.cp-recon { margin-top: 6px; min-height: 24px; }
@media (max-width: 1180px) { .cp-grid { grid-template-columns: repeat(3, minmax(0,1fr)); } }
@media (max-width: 900px) { .cp-grid, .cp-quality-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .cp-grid, .cp-quality-grid { grid-template-columns: 1fr; } .cockpit-summary__status { justify-items: start; } }
</style>
