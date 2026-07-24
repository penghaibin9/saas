<template>
  <AppPageShell
    title="学工统计驾驶舱"
    subtitle="困难认定 / 奖助 / 违纪 / 学生活动二课 各域概览一屏总览，点卡片下钻到分域统计。仅聚合口径。"
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
        </div>
      </div>

      <AppSectionCard title="全域总量">
        <div class="cp-totals">
          <div class="cp-total"><span>困难认定申请</span><b>{{ formatTotal(totals.aidApplications) }}</b></div>
          <div class="cp-total"><span>奖助申请</span><b>{{ formatTotal(totals.fundingApplications) }}</b></div>
          <div class="cp-total"><span>违纪案件</span><b>{{ formatTotal(totals.disciplineCases) }}</b></div>
          <div class="cp-total"><span>活动数</span><b>{{ formatTotal(totals.activities) }}</b></div>
        </div>
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
  data() { return { loading: true, errorMessage: '', domains: [], totals: {}, reconcileOk: true } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.load() },
  methods: {
    formatTotal(v) {
      return v === null || v === undefined ? '统计暂不可用' : v
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getStatsCockpit()
      if (res.code === 0 && res.data) {
        this.domains = res.data.domains || []
        this.totals = res.data.totals || {}
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
.cp-totals { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-3); }
.cp-total { display: flex; flex-direction: column; }
.cp-total span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cp-total b { font-size: var(--font-size-lg); }
.cp-recon { padding: var(--space-3); border-radius: var(--radius-md); }
.cp-recon.is-ok { background: rgba(34,197,94,0.08); }
.cp-recon.is-bad { background: rgba(239,68,68,0.08); }
@media (max-width: 960px) { .cp-grid, .cp-totals { grid-template-columns: 1fr 1fr; } }
</style>
