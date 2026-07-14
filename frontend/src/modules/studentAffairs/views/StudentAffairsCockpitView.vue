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
        <div v-for="d in domains" :key="d.key" class="cp-card" @click="go(d)">
          <div class="cp-card__label">{{ d.label }}</div>
          <div class="cp-card__total">{{ d.total }}</div>
          <div class="cp-card__hl">{{ d.highlightLabel }}：<b>{{ d.highlight }}</b></div>
          <div class="cp-card__more">查看分域统计 →</div>
        </div>
      </div>

      <AppSectionCard title="全域总量">
        <div class="cp-totals">
          <div class="cp-total"><span>困难认定申请</span><b>{{ totals.aidApplications || 0 }}</b></div>
          <div class="cp-total"><span>奖助申请</span><b>{{ totals.fundingApplications || 0 }}</b></div>
          <div class="cp-total"><span>违纪案件</span><b>{{ totals.disciplineCases || 0 }}</b></div>
          <div class="cp-total"><span>活动数</span><b>{{ totals.activities || 0 }}</b></div>
        </div>
        <div class="cp-recon" :class="reconcileOk ? 'is-ok' : 'is-bad'">
          处分投影对账：<StatusTag :type="reconcileOk ? 'success' : 'danger'" :label="reconcileOk ? '一致' : '不一致（需核查）'" dot />
        </div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsCockpitView',
  components: { AppGlobalState, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() { return { loading: true, errorMessage: '', domains: [], totals: {}, reconcileOk: true } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getStatsCockpit()
      if (res.code === 0 && res.data) {
        this.domains = res.data.domains || []
        this.totals = res.data.totals || {}
        this.reconcileOk = res.data.disciplineReconcileConsistent !== false
      } else {
        this.errorMessage = res.message || '驾驶舱加载失败'
      }
      this.loading = false
    },
    go(d) { if (d.route) this.$router.push(d.route) }
  }
}
</script>

<style scoped>
.cp-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.cp-card { border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: var(--space-4); cursor: pointer; background: var(--bg-card); transition: box-shadow .15s; }
.cp-card:hover { box-shadow: var(--shadow-card); border-color: var(--color-primary); }
.cp-card__label { color: var(--text-secondary); font-size: var(--font-size-sm); }
.cp-card__total { font-size: 32px; font-weight: 700; margin: var(--space-2) 0; }
.cp-card__hl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.cp-card__more { margin-top: var(--space-2); color: var(--color-primary); font-size: var(--font-size-xs); }
.cp-totals { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-3); }
.cp-total { display: flex; flex-direction: column; }
.cp-total span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cp-total b { font-size: var(--font-size-lg); }
.cp-recon { padding: var(--space-3); border-radius: var(--radius-md); }
.cp-recon.is-ok { background: rgba(34,197,94,0.08); }
.cp-recon.is-bad { background: rgba(239,68,68,0.08); }
@media (max-width: 960px) { .cp-grid, .cp-totals { grid-template-columns: 1fr 1fr; } }
</style>
