<template>
  <ModulePageShell
    title="教务看板"
    :subtitle="termSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <!-- 指标卡 -->
      <div class="aa-metric-grid">
        <AppMetricCard
          v-for="c in summaryCards"
          :key="c.key"
          :title="c.label"
          :value="c.value"
          :unit="c.unit || ''"
        />
        <EmptyState v-if="!summaryCards.length" title="暂无统计数据" description="当前数据范围内尚无可汇总的教务指标" />
      </div>

      <!-- 当前学期卡 -->
      <AppSectionCard title="当前学期">
        <div v-if="currentTerm && currentTerm.termId" class="aa-term-card">
          <div class="aa-term-card__main">
            <span class="aa-term-card__name">{{ currentTerm.yearCode }} 第 {{ currentTerm.termNo }} 学期</span>
            <AppStatusTag :status="currentTerm.status" dot>{{ statusLabel(currentTerm.status) }}</AppStatusTag>
          </div>
          <div class="aa-term-card__meta">
            <span>{{ termRange(currentTerm) }}</span>
            <span v-if="currentTerm.teachingWeeks">教学 {{ currentTerm.teachingWeeks }} 周</span>
            <span v-if="currentTerm.examWeekStart">考试周起 第 {{ currentTerm.examWeekStart }} 周</span>
          </div>
        </div>
        <EmptyState
          v-else
          title="尚未设置当前学期"
          description="到「学年学期」新建学期并发布，即可成为当前学期"
        >
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</button>
        </EmptyState>
      </AppSectionCard>

      <!-- 模块状态卡 -->
      <AppSectionCard title="教务模块" subtitle="LIVE=已上线 · 建设中=后续波次交付">
        <div class="aa-mod-grid">
          <div
            v-for="m in moduleCards"
            :key="m.key"
            class="aa-mod-cell"
            :class="{ 'is-live': m.status === 'LIVE' }"
          >
            <span class="aa-mod-cell__label">{{ m.label }}</span>
            <AppStatusTag :type="m.status === 'LIVE' ? 'success' : 'default'">
              {{ m.status === 'LIVE' ? 'LIVE' : '建设中' }}
            </AppStatusTag>
          </div>
        </div>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教务看板（/admin/academic-affairs）：GET /academic-affairs/dashboard。当前学期 + 指标卡 + 模块状态。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中' }

export default {
  name: 'AaDashboardView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppMetricCard, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      currentTerm: null,
      summaryCards: [],
      moduleCards: []
    }
  },
  computed: {
    termSubtitle() {
      if (this.currentTerm && this.currentTerm.termId) {
        return `当前学期：${this.currentTerm.yearCode} 第 ${this.currentTerm.termNo} 学期`
      }
      return '尚未设置当前学期 · 教务过程从「学年学期」开始'
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    termRange(t) {
      if (t.startDate && t.endDate) return `${t.startDate} ~ ${t.endDate}`
      return '起止日期未设置'
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getDashboard()
      if (res.code === 0) {
        const d = res.data || {}
        this.currentTerm = d.currentTerm || null
        this.summaryCards = d.summaryCards || []
        this.moduleCards = d.moduleCards || []
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.aa-term-card__main {
  display: flex;
  align-items: center;
  gap: 12px;
}
.aa-term-card__name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-900, #1f2329);
}
.aa-term-card__meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--text-500, #646a73);
  font-size: 13px;
}
.aa-mod-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.aa-mod-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid var(--border-200, #e5e6eb);
  border-radius: 8px;
  background: var(--fill-50, #f7f8fa);
}
.aa-mod-cell.is-live {
  background: var(--success-50, #eafff3);
  border-color: var(--success-200, #b7f0cf);
}
.aa-mod-cell__label {
  font-size: 14px;
  color: var(--text-700, #4e5969);
}
</style>
