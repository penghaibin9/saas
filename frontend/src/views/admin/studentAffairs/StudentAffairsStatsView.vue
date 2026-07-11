<template>
  <ModulePageShell
    title="学工统计"
    subtitle="关键指标 · 谈话工作量 · 宿舍入住 · 困难与处分 · 风险来源"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学工统计查阅"
  >
    <LoadingState v-if="loading" text="正在汇总学工统计…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <!-- 关键指标 -->
      <section class="st-block">
        <h3 class="st-block__title">关键指标</h3>
        <div class="st-cards">
          <div v-for="c in summaryCards" :key="c.key" class="st-card">
            <span class="st-card__value">{{ c.value }}<i>{{ c.unit }}</i></span>
            <span class="st-card__label">{{ c.label }}</span>
          </div>
        </div>
      </section>

      <div class="st-grid">
        <!-- 谈话工作量 -->
        <section class="st-panel">
          <h3 class="st-panel__title">谈话工作量</h3>
          <div class="st-big">完成率 <b>{{ talkRate }}%</b><span>（{{ talkStats.completed || 0 }}/{{ talkStats.total || 0 }}）</span></div>
          <div v-for="b in talkBreakdown" :key="b.key" class="st-bar">
            <div class="st-bar__head"><span>{{ talkTypeLabel(b.key) }}</span><span>{{ b.completed }}/{{ b.total }}</span></div>
            <div class="st-bar__track"><div class="st-bar__fill" :style="{ width: pct(b.completed, b.total) + '%' }" /></div>
          </div>
          <EmptyState v-if="!talkBreakdown.length" title="暂无谈话数据" />
        </section>

        <!-- 宿舍入住 -->
        <section class="st-panel">
          <h3 class="st-panel__title">宿舍入住</h3>
          <div class="st-big">入住率 <b>{{ occRate }}%</b><span>（{{ occupancy.occupiedBeds || 0 }}/{{ occupancy.totalBeds || 0 }} 床）</span></div>
          <div class="st-bar">
            <div class="st-bar__track"><div class="st-bar__fill st-bar__fill--green" :style="{ width: occRate + '%' }" /></div>
          </div>
          <div class="st-kv"><span>已住</span><b>{{ occupancy.occupiedBeds || 0 }}</b></div>
          <div class="st-kv"><span>空床</span><b>{{ occupancy.vacantBeds || 0 }}</b></div>
          <div class="st-kv"><span>总床位</span><b>{{ occupancy.totalBeds || 0 }}</b></div>
        </section>

        <!-- 困难与处分 -->
        <section class="st-panel">
          <h3 class="st-panel__title">困难与处分</h3>
          <div class="st-kv"><span>困难学生库</span><b>{{ difficultCount }} 人</b></div>
          <div class="st-kv"><span>处分生效</span><b>{{ reconcile.effectiveCases ?? '—' }} 条</b></div>
          <div class="st-kv"><span>投影行数</span><b>{{ reconcile.activeProjections ?? '—' }} 行</b></div>
          <div class="st-kv">
            <span>投影一致性</span>
            <b :class="reconcile.consistent ? 'st-ok' : 'st-bad'">{{ reconcile.consistent ? '一致 ✓' : '不一致 ✗' }}</b>
          </div>
        </section>

        <!-- 风险来源分布 -->
        <section class="st-panel">
          <h3 class="st-panel__title">风险来源分布（在办）</h3>
          <div v-for="s in riskBySource" :key="s.key" class="st-bar">
            <div class="st-bar__head"><span>{{ sourceLabel(s.key) }}</span><span>{{ s.count }}</span></div>
            <div class="st-bar__track"><div class="st-bar__fill st-bar__fill--red" :style="{ width: pct(s.count, riskMax) + '%' }" /></div>
          </div>
          <EmptyState v-if="!riskBySource.length" title="暂无在办风险" />
        </section>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 学工统计（/admin/student-affairs/stats）—— 13A 只读统计总览。
 * 真实聚合：dashboard 关键指标 + talks/stats 谈话完成率 + dorm/occupancy 入住率 +
 * discipline/reconcile 投影对账 + aid/difficult-students 困难库 + 风险按来源分组（客户端）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TALK_TYPE = { DAILY: '日常', ACADEMIC: '学业', PSYCHOLOGY: '心理', DISCIPLINE: '违纪', EMPLOYMENT: '就业', INTERNSHIP: '实习', AID: '资助', DORM: '宿舍' }
const SOURCE_LABEL = { LEAVE_OVERDUE: '请假逾期', ACADEMIC_WARNING: '学业预警', DORM: '宿舍异常', MENTAL: '心理关注', DISCIPLINE: '违纪', INTERNSHIP: '实习异常', GRADUATION_DESIGN: '毕设', EMPLOYMENT: '就业', FAMILY: '家庭', MANUAL: '手动登记' }

export default {
  name: 'StudentAffairsStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, error: '',
      summaryCards: [], talkStats: {}, occupancy: {}, reconcile: {}, difficultCount: 0, riskBySource: []
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    talkRate() {
      return Math.round((this.talkStats.completionRate || 0) * 100)
    },
    talkBreakdown() {
      return (this.talkStats.breakdown || []).filter((b) => b.key)
    },
    occRate() {
      const o = this.occupancy
      if (!o.totalBeds) return 0
      return Math.round((o.occupiedBeds / o.totalBeds) * 100)
    },
    riskMax() {
      return Math.max(1, ...this.riskBySource.map((s) => s.count))
    }
  },
  created() {
    this.load()
  },
  methods: {
    pct(a, b) {
      if (!b) return 0
      return Math.round((a / b) * 100)
    },
    talkTypeLabel(t) {
      return TALK_TYPE[t] || t || '其他'
    },
    sourceLabel(s) {
      return SOURCE_LABEL[s] || s
    },
    async load() {
      this.loading = true
      this.error = ''
      const [dash, talk, occ, rec, diff, risks] = await Promise.all([
        studentAffairsApi.getDashboard(),
        studentAffairsApi.getTalkStats('TYPE'),
        studentAffairsApi.getOccupancy(),
        studentAffairsApi.reconcileDiscipline(),
        studentAffairsApi.getDifficultStudents({ page: 1, pageSize: 200 }),
        studentAffairsApi.getRisks({ page: 1, pageSize: 200 })
      ])
      this.loading = false
      if (dash.code !== 0) { this.error = dash.message || '统计加载失败'; return }
      this.summaryCards = (dash.data && dash.data.summaryCards) || []
      this.talkStats = (talk.code === 0 && talk.data) || {}
      this.occupancy = (occ.code === 0 && occ.data) || {}
      this.reconcile = (rec.code === 0 && rec.data) || {}
      this.difficultCount = (diff.code === 0 && diff.data && (diff.data.items || []).length) || 0
      // 风险按来源分组（仅在办：status !== CLOSED）
      const items = (risks.code === 0 && risks.data && risks.data.items) || []
      const map = {}
      items.filter((r) => r.status !== 'CLOSED').forEach((r) => { map[r.source] = (map[r.source] || 0) + 1 })
      this.riskBySource = Object.entries(map).map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count)
    }
  }
}
</script>

<style scoped>
.st-block {
  margin-bottom: var(--space-5);
}
.st-block__title,
.st-panel__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
}
.st-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--space-3);
}
.st-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
}
.st-card__value {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}
.st-card__value i {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--text-tertiary);
  font-style: normal;
  margin-left: 2px;
}
.st-card__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.st-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
}
.st-panel {
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
}
.st-big {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.st-big b {
  font-size: var(--font-size-xl);
  color: var(--primary-700);
  margin: 0 var(--space-1);
}
.st-big span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.st-bar {
  margin-bottom: var(--space-2);
}
.st-bar__head {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.st-bar__track {
  height: 8px;
  background: var(--bg-muted, #f0f0f0);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.st-bar__fill {
  height: 100%;
  background: var(--primary-500);
  border-radius: var(--radius-full);
}
.st-bar__fill--green {
  background: var(--success-500, #22c55e);
}
.st-bar__fill--red {
  background: var(--danger-500, #ef4444);
}
.st-kv {
  display: flex;
  justify-content: space-between;
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-subtle, #f0f0f0);
}
.st-kv b {
  color: var(--text-primary);
}
.st-ok {
  color: var(--success-700, #15803d);
}
.st-bad {
  color: var(--danger-600, #dc2626);
}
</style>
