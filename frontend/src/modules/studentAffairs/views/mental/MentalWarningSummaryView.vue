<template>
  <AppPageShell
    title="心理预警摘要"
    subtitle="面向管理侧的非敏感视图：仅呈现「是否需关注 / 关注等级 / 在办危机数」等聚合与标记，绝不含任何心理明细。"
    role-name="学工处 / 学院 / 辅导员（仅摘要）"
    data-scope-name="学工数据范围（明细另受 PSY_STUDENT 约束）"
    watermark-purpose="心理预警摘要查看"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载心理预警摘要..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="按关注等级分布（聚合）">
        <table class="sa-table">
          <thead>
            <tr><th>关注等级</th><th>数量</th></tr>
          </thead>
          <tbody>
            <tr v-for="lv in levelRows" :key="lv.key">
              <td><AppStatusTag :type="lv.kind" :label="lv.label" /></td>
              <td>{{ lv.value }}</td>
            </tr>
            <tr v-if="!levelRows.length"><td colspan="2" class="sa-empty">暂无数据</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard title="按学生查预警摘要（无明细）">
        <div class="sa-toolbar">
          <AppSearchBox v-model="queryStudentId" class="sa-input" placeholder="输入学生 ID 查询摘要" :debounce="0" @search="querySummary" />
          <AppPermissionButton code="studentAffairs.risk.view" variant="secondary" :loading="actioning" @click="querySummary">
            查询摘要
          </AppPermissionButton>
        </div>
        <div v-if="summary" class="sa-summary">
          <div class="sa-summary__item">
            <span>是否需关注</span>
            <strong :class="summary.needAttention ? 'sa-warn' : 'sa-ok'">{{ summary.needAttention ? '需关注' : '暂无' }}</strong>
          </div>
          <div class="sa-summary__item">
            <span>关注等级</span>
            <strong>{{ summary.attentionLabel || '—' }}</strong>
          </div>
          <div class="sa-summary__item">
            <span>在办转介</span>
            <strong>{{ summary.openReferralCount }}</strong>
          </div>
          <div class="sa-summary__item">
            <span>在办危机风险</span>
            <strong :class="summary.openCrisisRiskCount ? 'sa-warn' : 'sa-ok'">{{ summary.openCrisisRiskCount }}</strong>
          </div>
          <p class="sa-note">本视图仅返回标记与计数，不含任何咨询记录/诊断/明细。</p>
        </div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppSearchBox,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const LEVELS = [
  { key: 'CRISIS', label: '危机', kind: 'danger' },
  { key: 'FOCUS', label: '重点关注', kind: 'warning' },
  { key: 'GENERAL', label: '一般关注', kind: 'info' }
]

export default {
  name: 'MentalWarningSummaryView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSearchBox, AppSectionCard, AppStatusTag },
  data() {
    return { loading: true, actioning: false, errorMessage: '', stats: null, queryStudentId: '', summary: null }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const s = this.stats || {}
      const byStatus = s.byStatus || {}
      return [
        { key: 'total', label: '关注在册', value: s.total || 0, accent: 'primary' },
        { key: 'crisis', label: '在办危机', value: s.openCrisis || 0, accent: (s.openCrisis || 0) ? 'risk' : 'success' },
        { key: 'following', label: '回访中', value: byStatus.FOLLOWING || 0, accent: 'warning' },
        { key: 'referred', label: '待跟进', value: byStatus.REFERRED || 0, accent: 'info' }
      ]
    },
    levelRows() {
      const byLevel = (this.stats && this.stats.byLevel) || {}
      return LEVELS.filter((lv) => byLevel[lv.key] !== undefined)
        .map((lv) => ({ ...lv, value: byLevel[lv.key] || 0 }))
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getMentalStats()
        this.stats = res.data || {}
      } catch (e) {
        this.errorMessage = e.message || '心理预警摘要加载失败'
      } finally {
        this.loading = false
      }
    },
    async querySummary() {
      if (!this.queryStudentId) return
      this.actioning = true
      this.summary = null
      try {
        const res = await studentAffairsApi.getMentalSummary(this.queryStudentId.trim())
        this.summary = res.data
      } catch (e) {
        this.errorMessage = e.message || '查询学生摘要失败'
      } finally {
        this.actioning = false
      }
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.sa-input {
  width: 260px;
}
.sa-table {
  width: 100%;
  border-collapse: collapse;
}
.sa-table th,
.sa-table td {
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-3);
  text-align: left;
}
.sa-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.sa-summary__item {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.sa-summary__item span {
  color: var(--text-tertiary);
}
.sa-summary__item strong {
  font-size: var(--font-size-lg);
}
.sa-warn {
  color: var(--warning-700);
}
.sa-ok {
  color: var(--success-700);
}
.sa-note {
  grid-column: 1 / -1;
  color: var(--text-tertiary);
  margin: 0;
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-summary {
    grid-template-columns: 1fr;
  }
}
</style>
