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
      <section class="sa-summary-strip mental-summary-privacy">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">非敏感管理视图</span>
          <h2 class="sa-summary-strip__title">本页只回答“是否需要关注、处于什么等级、还有多少在办记录”，绝不展示咨询原文或心理明细</h2>
          <p class="sa-summary-strip__text">管理人员可先看聚合分布，再按学生查询必要摘要。确需查看明细时必须进入心理关注名单，并通过专项权限、逐生范围和敏感查看审计。</p>
        </div>
      </section>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <div class="mental-summary-layout">
        <AppSectionCard title="关注等级分布（仅聚合）">
          <p class="mental-section-hint">只显示当前数据范围内各关注等级数量，不包含学生心理明细。</p>
          <DataTable v-if="levelRows.length" :columns="levelColumns" :rows="levelRows" row-key="key">
            <template #cell-label="{ row }"><AppStatusTag :type="row.kind" :label="row.label" /></template>
            <template #cell-value="{ row }"><strong class="mental-count">{{ row.value }}</strong></template>
          </DataTable>
          <p v-else class="sa-empty">当前数据范围内暂无心理预警聚合数据。</p>
        </AppSectionCard>

        <AppSectionCard title="按学生查询必要摘要">
          <p class="mental-section-hint">选择当前数据范围内学生，仅返回关注标记、等级和在办数量。</p>
          <div class="sa-toolbar sa-filter-bar">
            <AppStudentPicker v-model="queryStudentId" class="sa-input" placeholder="按学号 / 姓名选择学生"
              data-scope-hint="仅显示你数据范围内的学生" @change="querySummary" />
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" :loading="actioning" @click="querySummary">
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
            <p class="sa-note">本视图仅返回标记与计数，不含任何咨询记录、诊断或明细。</p>
          </div>
          <p v-else class="mental-query-empty">选择学生后，摘要结果会显示在这里。</p>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppStudentPicker,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const LEVEL_COLUMNS = [{ key: 'label', title: '关注等级' }, { key: 'value', title: '数量' }]
const LEVELS = [
  { key: 'CRISIS', label: '危机', kind: 'danger' },
  { key: 'FOCUS', label: '重点关注', kind: 'warning' },
  { key: 'GENERAL', label: '一般关注', kind: 'info' }
]

export default {
  name: 'MentalWarningSummaryView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppStudentPicker, AppSectionCard, AppStatusTag, DataTable },
  props: { ctx: { type: Object, default: null } },
  data() {
    return { levelColumns: LEVEL_COLUMNS, loading: true, actioning: false, errorMessage: '', stats: null, queryStudentId: '', summary: null }
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
    canBtn(code) { return canCode(this.ctx, code) },
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
        const res = await studentAffairsApi.getMentalSummary(String(this.queryStudentId).trim())
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
.mental-summary-privacy { border-color: var(--warning-300, #fcd34d); background: var(--warning-50, #fffbeb); }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.mental-summary-layout { display: grid; grid-template-columns: minmax(280px, .75fr) minmax(0, 1.25fr); gap: var(--space-4); align-items: start; }
.mental-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.sa-toolbar { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-3); }
.sa-input { flex: 1 1 260px; min-width: 220px; }
.mental-count { color: var(--primary-700); font-size: var(--font-size-lg); font-variant-numeric: tabular-nums; }
.sa-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.sa-summary__item { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-2); background: var(--bg-section); }
.sa-summary__item span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sa-summary__item strong { font-size: var(--font-size-lg); font-variant-numeric: tabular-nums; }
.sa-warn { color: var(--warning-700); }
.sa-ok { color: var(--success-700); }
.sa-note { grid-column: 1 / -1; color: var(--text-tertiary); margin: 0; font-size: var(--font-size-xs); line-height: 1.6; }
.mental-query-empty { margin: 0; padding: var(--space-5); border: 1px dashed var(--border-base); border-radius: var(--radius-md); color: var(--text-tertiary); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics, .mental-summary-layout { grid-template-columns: 1fr 1fr; } .mental-summary-layout { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics, .sa-summary { grid-template-columns: 1fr; } .sa-input { width: 100%; min-width: 0; } }
@import '@/styles/module-page.css';
</style>
