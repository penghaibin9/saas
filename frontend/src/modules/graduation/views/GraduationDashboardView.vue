<template>
  <ModulePageShell
    title="毕业设计中心"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="顶部批次条选择当前工作批次后，再查看本批次运营总览。"
    >
      <template #actions>
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/batches?panel=create')">＋ 新增毕设批次</button>
        <button class="mp-btn" @click="$router.push('/admin/graduation/batches?panel=list')">去批次列表</button>
      </template>
    </EmptyState>

    <div v-else class="mp-stack gdb-page">
      <section class="gdb-overview" aria-label="今日毕业设计结论">
        <div class="gdb-overview__conclusion">
          <span class="gdb-overview__eyebrow">今日结论</span>
          <strong>{{ priorityConclusion }}</strong>
          <p>{{ priorityDetail }}</p>
        </div>
        <div class="gdb-kpis" aria-label="当前批次关键指标">
          <div v-for="s in keyStats" :key="s.label" class="gdb-kpi">
            <span class="gdb-kpi__value">{{ s.value }}</span>
            <span class="gdb-kpi__label">{{ s.label }}</span>
            <span v-if="s.trend" class="gdb-kpi__trend">{{ s.trend }}</span>
          </div>
        </div>
      </section>

      <div class="mp-grid-2 gdb-priority-grid">
        <section class="mp-card gdb-priority-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日优先</span>
            <button class="mp-link" @click="goWithBatch('/admin/graduation/students')">毕设学生 →</button>
          </div>
          <div class="mp-card__body gdb-todos">
            <button
              v-for="t in hero.todos"
              :key="t.id"
              class="gdb-todo"
              :class="'is-' + t.tone"
              type="button"
              @click="goTodo(t)"
            >
              <span class="gdb-todo__count">{{ t.count }}</span>
              <span class="gdb-todo__copy">
                <span class="gdb-todo__label">{{ t.label }}</span>
                <span class="gdb-todo__hint">{{ t.hint }}</span>
              </span>
              <span class="gdb-todo__action">去处理 <b>→</b></span>
            </button>
          </div>
        </section>

        <section class="mp-card gdb-risk-card">
          <div class="mp-card__head">
            <span class="mp-card__title">滞后与风险提醒</span>
            <button class="mp-link" @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'risk' })">风险台账 →</button>
          </div>
          <div class="mp-card__body">
            <div v-if="!hero.riskAlerts.length" class="gdb-risk-empty">
              <span class="gdb-risk-empty__icon">✓</span>
              <div>
                <strong>暂未发现待处理风险</strong>
                <p>风险扫描结果会在这里集中展示。</p>
              </div>
            </div>
            <div v-else class="gdb-risks">
              <button
                v-for="r in hero.riskAlerts"
                :key="r.id"
                class="gdb-risk-row"
                :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'"
                type="button"
                @click="goRisk(r)"
              >
                <span class="gdb-risk-row__main">
                  <span class="gdb-risk-row__title">{{ r.code }} · {{ r.title }}</span>
                  <span class="gdb-risk-row__detail">{{ r.detail }}</span>
                </span>
                <RiskTag :level="r.level" />
                <span class="gdb-risk-row__action">处置 →</span>
              </button>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card gdb-progress-card">
        <div class="mp-card__head">
          <span class="mp-card__title">当前批次整体进度</span>
          <span class="gdb-progress-card__meta">{{ hero.batchName || batchStore.selectedBatchName }} · {{ hero.batchStatus || batchStore.batchStatus || '—' }}</span>
        </div>
        <div class="mp-card__body gdb-flow">
          <div v-for="f in hero.flow" :key="f.label" class="gdb-flow__item" :class="{ 'is-active': f.active }">
            <span class="gdb-flow__value">{{ f.value }}</span>
            <span class="gdb-flow__label">{{ f.label }}</span>
          </div>
        </div>
      </section>

      <section v-if="hero.moduleStats && hero.moduleStats.length" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">跨模块统计</span>
          <button class="mp-link" @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'stats' })">完整统计 →</button>
        </div>
        <div class="mp-card__body gdb-modstats">
          <button
            v-for="s in hero.moduleStats"
            :key="s.label"
            class="gdb-modstat"
            type="button"
            @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'stats' })"
          >
            <div class="gdb-modstat__val">{{ s.value }}</div>
            <div class="gdb-modstat__label">{{ s.label }}</div>
            <div class="gdb-modstat__hint">{{ s.hint }}</div>
          </button>
        </div>
      </section>

      <p class="mp-note">看板数字来自当前批次与当前数据范围；待办和风险均可带着 batch/filter 直接下钻到真实处理队列。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕业设计中心 · 管理看板（/admin/graduation）。 */
import { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const TODO_TARGETS = {
  t1: { path: '/admin/graduation/proposals', query: { tab: 'PENDING_REVIEW' } },
  t2: { path: '/admin/graduation/proposals', query: { tab: 'NOT_SUBMITTED' } },
  t3: { path: '/admin/graduation/finals', query: { tab: 'PENDING_REVIEW' } },
  t4: { path: '/admin/graduation/defense', query: {} },
  t5: { path: '/admin/graduation/risk-archive', query: { panel: 'risk' } }
}

export default {
  name: 'GraduationDashboardView',
  components: { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      error: '',
      hero: { stats: [], flow: [], todos: [], riskAlerts: [], moduleStats: [], batchName: '', batchRange: '', batchStatus: '' }
    }
  },
  computed: {
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const name = this.hero.batchName || this.batchStore.selectedBatchName || '当前批次'
      const status = this.hero.batchStatus || this.batchStore.batchStatus || ''
      return status ? `${name} · ${status}` : name
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createBatch', label: '＋ 新增毕设批次', variant: 'primary' },
        { key: 'importStudents', label: '导入学生名单' },
        { key: 'exportStats', label: '导出进度统计' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({
          ...a,
          disabled: !pa[a.key].allowed || (a.key !== 'createBatch' && a.key !== 'viewAuditLog' && !this.hasBatch),
          disabledReason: pa[a.key].reason
        }))
    },
    keyStats() {
      return (this.hero.stats || []).slice(0, 5)
    },
    todoLoad() {
      return (this.hero.todos || []).reduce((sum, item) => sum + Math.max(0, Number(item.count) || 0), 0)
    },
    highRiskCount() {
      const stat = (this.hero.stats || []).find((item) => item.label === '高风险学生')
      return Math.max(0, Number(stat?.value) || 0)
    },
    priorityTodo() {
      return (this.hero.todos || [])
        .filter((item) => Number(item.count) > 0)
        .slice()
        .sort((a, b) => Number(b.count) - Number(a.count))[0] || null
    },
    priorityConclusion() {
      if (!this.todoLoad && !this.highRiskCount) return '当前批次暂无待处理事项，继续关注过程进度与后续风险。'
      if (this.highRiskCount) return `今日待办量 ${this.todoLoad}，其中高风险 ${this.highRiskCount} 条；先处理高风险学生。`
      return this.priorityTodo
        ? `今日待办量 ${this.todoLoad}；先处理「${this.priorityTodo.label}」。`
        : `今日待办量 ${this.todoLoad}。`
    },
    priorityDetail() {
      return '全部数字均按当前批次与当前角色数据范围统计；处理完成后返回看板复核待办和风险变化。'
    }
  },
  created() {
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.load()
    }
  },
  methods: {
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.hero = { stats: [], flow: [], todos: [], riskAlerts: [], moduleStats: [], batchName: '', batchRange: '', batchStatus: '' }
        return
      }
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId })
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    routeWithBatch(path, query = {}) {
      const [pathname, rawQuery = ''] = String(path || '').split('?')
      const inherited = Object.fromEntries(new URLSearchParams(rawQuery))
      const batchId = this.batchStore.selectedBatchId
      return {
        path: pathname,
        query: { ...inherited, ...query, ...(batchId ? { batchId: String(batchId) } : {}) }
      }
    },
    goWithBatch(path, query = {}) {
      this.$router.push(this.routeWithBatch(path, query))
    },
    todoTarget(todo) {
      const target = TODO_TARGETS[todo?.id] || { path: todo?.route || '/admin/graduation', query: {} }
      return this.routeWithBatch(target.path, target.query)
    },
    goTodo(todo) {
      this.$router.push(this.todoTarget(todo))
    },
    goRisk(risk) {
      this.$router.push(this.routeWithBatch('/admin/graduation/risk-archive', {
        panel: 'risk',
        ...(risk?.id ? { rsel: String(risk.id) } : {})
      }))
    },
    onToolbar(key) {
      if (key === 'createBatch') {
        this.$router.push('/admin/graduation/batches?panel=create')
        return
      }
      const map = {
        importStudents: { path: '/admin/graduation/students', query: { panel: 'roster' } },
        exportStats: { path: '/admin/graduation/risk-archive', query: { panel: 'stats' } },
        viewAuditLog: { path: '/admin/graduation/audit-logs', query: {} }
      }
      const target = map[key]
      if (target) this.goWithBatch(target.path, target.query)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gdb-page { gap: var(--space-3); }
.gdb-overview {
  display: grid;
  grid-template-columns: minmax(280px, .9fr) minmax(0, 1.5fr);
  gap: var(--space-4);
  align-items: stretch;
  padding: var(--space-4);
  border-radius: var(--radius-lg, 12px);
  color: #fff;
  background: linear-gradient(120deg, var(--primary-900, #123a78), var(--primary-600, #2563eb));
  box-shadow: 0 10px 28px rgba(37, 99, 235, .16);
}
.gdb-overview__conclusion { align-self: center; min-width: 0; }
.gdb-overview__eyebrow { display: block; margin-bottom: 5px; color: rgba(255, 255, 255, .72); font-size: var(--font-size-xs); font-weight: 600; letter-spacing: .08em; }
.gdb-overview__conclusion strong { display: block; font-size: 18px; line-height: 1.45; }
.gdb-overview__conclusion p { margin: 7px 0 0; color: rgba(255, 255, 255, .75); font-size: var(--font-size-xs); line-height: 1.55; }
.gdb-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.gdb-kpi { min-width: 0; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, .16); border-radius: var(--radius-md); background: rgba(255, 255, 255, .08); }
.gdb-kpi__value { display: block; font-size: 22px; font-weight: 700; line-height: 1.2; }
.gdb-kpi__label { display: block; margin-top: 4px; color: rgba(255, 255, 255, .86); font-size: var(--font-size-xs); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gdb-kpi__trend { display: block; margin-top: 2px; color: rgba(255, 255, 255, .62); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gdb-priority-grid { align-items: stretch; }
.gdb-priority-card, .gdb-risk-card { min-height: 0; }
.gdb-todos { display: grid; gap: 6px; }
.gdb-todo { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); width: 100%; padding: 8px 10px; border: 1px solid transparent; border-radius: var(--radius-md); background: transparent; color: inherit; text-align: left; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
.gdb-todo:hover { background: var(--gray-50); border-color: var(--border-light); }
.gdb-todo:focus-visible, .gdb-modstat:focus-visible, .gdb-risk-row:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.gdb-todo__count { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--radius-full); color: var(--primary-700, #1d4ed8); background: var(--primary-50, #eff6ff); font-weight: var(--font-weight-bold); }
.gdb-todo.is-danger .gdb-todo__count { color: var(--danger-700, #b91c1c); background: var(--danger-50, #fef2f2); }
.gdb-todo__copy { display: grid; gap: 2px; min-width: 0; }
.gdb-todo__label { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.gdb-todo__hint { overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gdb-todo__action { color: var(--text-link, var(--pri, #2563eb)); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); white-space: nowrap; }
.gdb-todo__action b { font-size: 16px; font-weight: 400; }
.gdb-risks { display: grid; gap: 6px; }
.gdb-risk-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: var(--space-2); width: 100%; padding: 9px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--card); color: inherit; text-align: left; cursor: pointer; }
.gdb-risk-row:hover { border-color: var(--primary-200, #bfdbfe); background: var(--gray-50); }
.gdb-risk-row.is-danger { border-left: 3px solid var(--danger-400, #f87171); }
.gdb-risk-row.is-warning { border-left: 3px solid var(--warning-400, #fbbf24); }
.gdb-risk-row__main { display: grid; gap: 2px; min-width: 0; }
.gdb-risk-row__title { overflow: hidden; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.gdb-risk-row__detail { overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gdb-risk-row__action { color: var(--text-link); font-size: var(--font-size-xs); white-space: nowrap; }
.gdb-risk-empty { display: flex; align-items: center; gap: var(--space-3); min-height: 142px; color: var(--text-secondary); }
.gdb-risk-empty__icon { display: grid; place-items: center; flex: 0 0 auto; width: 34px; height: 34px; border-radius: var(--radius-full); background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); font-weight: var(--font-weight-bold); }
.gdb-risk-empty strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.gdb-risk-empty p { margin: 4px 0 0; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gdb-progress-card__meta { margin-left: auto; color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.gdb-flow { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 8px; }
.gdb-flow__item { position: relative; display: grid; justify-items: center; gap: 4px; min-width: 0; padding: 8px 4px; border-radius: var(--radius-md); background: var(--gray-50); }
.gdb-flow__item.is-active { background: var(--primary-50, #eff6ff); }
.gdb-flow__value { color: var(--primary-700, #1d4ed8); font-size: 18px; font-weight: 700; }
.gdb-flow__label { overflow: hidden; max-width: 100%; color: var(--text-secondary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gdb-modstats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.gdb-modstat { padding: 10px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--card); color: inherit; text-align: left; cursor: pointer; }
.gdb-modstat:hover { background: var(--gray-50); border-color: var(--primary-200, #bfdbfe); }
.gdb-modstat__val { color: var(--primary-700, #1d4ed8); font-size: 18px; font-weight: 700; }
.gdb-modstat__label { margin-top: 2px; color: var(--text-primary); font-size: var(--font-size-xs); font-weight: 600; }
.gdb-modstat__hint { margin-top: 2px; overflow: hidden; color: var(--text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 1180px) {
  .gdb-overview { grid-template-columns: 1fr; }
  .gdb-kpis { grid-template-columns: repeat(5, minmax(110px, 1fr)); overflow-x: auto; }
  .gdb-flow { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .gdb-priority-grid { grid-template-columns: 1fr; }
  .gdb-overview { padding: var(--space-3); }
  .gdb-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); overflow: visible; }
  .gdb-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gdb-modstats { grid-template-columns: 1fr; }
}
</style>
