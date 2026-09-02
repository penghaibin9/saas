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
          <span class="gdb-overview__eyebrow">先看结论，再处理任务</span>
          <strong>{{ priorityConclusion }}</strong>
          <p>{{ priorityDetail }}</p>
          <div class="gdb-overview__context" aria-label="当前工作范围">
            <span>{{ hero.batchName || batchStore.selectedBatchName || '当前批次' }}</span>
            <span>{{ ctx.currentRole.roleName }}</span>
            <span>{{ ctx.dataScope.scopeName }}</span>
          </div>
        </div>
        <div class="gdb-kpis" aria-label="当前批次关键指标">
          <div v-for="s in keyStats" :key="s.label" class="gdb-kpi">
            <span class="gdb-kpi__value">{{ s.value }}</span>
            <span class="gdb-kpi__label">{{ s.label }}</span>
            <span v-if="s.trend" class="gdb-kpi__trend">{{ s.trend }}</span>
          </div>
        </div>
      </section>

      <section class="mp-card gdb-work" aria-label="今天先做这些">
        <div class="mp-card__head gdb-work__head">
          <div>
            <span class="gdb-work__eyebrow">已按紧急度和职责排好顺序</span>
            <span class="mp-card__title">今天先做这些</span>
          </div>
          <div class="gdb-work__summary">
            <span>{{ workItems.length }} 项在手</span>
            <small v-if="workItems.length">逐项处理后回到这里复核</small>
          </div>
        </div>
        <div v-if="workItems.length" class="mp-card__body gdb-work-list">
          <article
            v-for="(item, index) in workItems"
            :key="workItemKey(item, index)"
            class="gdb-work-item"
            :class="[priorityClass(item.priority), { 'is-lead': index === 0 }]"
          >
            <div class="gdb-work-item__priority">
              <span>{{ priorityLabel(item.priority) }}</span>
              <small v-if="index === 0">先处理</small>
            </div>
            <div class="gdb-work-item__main">
              <div class="gdb-work-item__identity">
                <strong>{{ item.student?.name || '待确认对象' }}</strong>
                <span>{{ item.business || '毕业设计事项' }}</span>
                <small v-if="studentMeta(item.student)">{{ studentMeta(item.student) }}</small>
              </div>
              <p>{{ item.whyHere || '请进入任务查看当前情况。' }}</p>
              <div class="gdb-work-item__facts">
                <span><b>当前等待</b>{{ item.waitingOn || '待确认' }}</span>
                <span><b>下一责任人</b>{{ item.nextActor || '待确认' }}</span>
                <span v-if="item.dueAt"><b>要求完成</b>{{ item.dueAt }}</span>
                <span><b>最近变化</b>{{ item.recentChange || '暂无新变化' }}</span>
              </div>
            </div>
            <button
              type="button"
              class="mp-btn mp-btn--primary gdb-work-item__action"
              :aria-label="`${item.primaryAction?.label || '去处理'}：${item.student?.name || item.business || '毕业设计事项'}`"
              @click="goWorkItem(item)"
            >
              {{ item.primaryAction?.label || '去处理' }} →
            </button>
          </article>
        </div>
        <div v-else class="mp-card__body gdb-work-empty">
          <span>✓</span>
          <div>
            <strong>当前职责范围内没有紧急工作</strong>
            <p>可以继续查看本批次整体进度与后续风险。</p>
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
              <span class="gdb-todo__action">去队列 <b>→</b></span>
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

      <p class="mp-note">看板数字来自当前批次与当前数据范围；工作项沿用服务端顺序，操作会带着当前批次和筛选条件进入真实处理队列。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕业设计中心 · 管理看板（/admin/graduation）。 */
import { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const EMPTY_HERO = () => ({
  stats: [],
  flow: [],
  todos: [],
  todayWorkItems: [],
  riskAlerts: [],
  moduleStats: [],
  batchName: '',
  batchRange: '',
  batchStatus: ''
})

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
      hero: EMPTY_HERO()
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
      const pa = this.ctx.permissionActions || {}
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
      return (Array.isArray(this.hero.stats) ? this.hero.stats : []).slice(0, 5)
    },
    workItems() {
      return Array.isArray(this.hero.todayWorkItems) ? this.hero.todayWorkItems : []
    },
    firstWorkItem() {
      return this.workItems[0] || null
    },
    todoLoad() {
      return (Array.isArray(this.hero.todos) ? this.hero.todos : [])
        .reduce((sum, item) => sum + Math.max(0, Number(item.count) || 0), 0)
    },
    highRiskCount() {
      const stat = (Array.isArray(this.hero.stats) ? this.hero.stats : [])
        .find((item) => item.label === '高风险学生')
      return Math.max(0, Number(stat?.value) || 0)
    },
    priorityTodo() {
      return (Array.isArray(this.hero.todos) ? this.hero.todos : [])
        .filter((item) => Number(item.count) > 0)
        .slice()
        .sort((a, b) => Number(b.count) - Number(a.count))[0] || null
    },
    priorityConclusion() {
      const first = this.firstWorkItem
      if (first) return `先处理「${first.student?.name || first.business} · ${first.business}」。`
      if (!this.todoLoad && !this.highRiskCount) return '当前批次暂无待处理事项，继续关注过程进度与后续风险。'
      if (this.highRiskCount) return `今日待办量 ${this.todoLoad}，其中高风险 ${this.highRiskCount} 条；先处理高风险学生。`
      return this.priorityTodo
        ? `今日待办量 ${this.todoLoad}；先处理「${this.priorityTodo.label}」。`
        : `今日待办量 ${this.todoLoad}。`
    },
    priorityDetail() {
      const first = this.firstWorkItem
      return first?.whyHere || '全部数字均按当前批次与当前角色数据范围统计；处理完成后返回看板复核待办和风险变化。'
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
        this.hero = EMPTY_HERO()
        return
      }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId })
        if (res.code === 0) this.hero = { ...EMPTY_HERO(), ...(res.data || {}) }
        else this.error = res.message || '毕业设计总览加载失败，请稍后重试。'
      } catch (error) {
        this.error = error?.message || '毕业设计总览加载失败，请检查网络后重试。'
      } finally {
        this.loading = false
      }
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
    workItemKey(item, index) {
      return item?.id || `${item?.priority || 'NORMAL'}-${item?.student?.id || item?.student?.name || 'item'}-${index}`
    },
    priorityClass(priority) {
      return `is-${String(priority || 'NORMAL').toLowerCase()}`
    },
    priorityLabel(priority) {
      return {
        CRITICAL: '立即处理', HIGH: '高优先', OVERDUE: '已逾期', DUE_24H: '24 小时内',
        RELEASE_BLOCKER: '阻塞发布', RETURNED: '已退回', WAITING_REVIEW: '等待评阅', NORMAL: '常规'
      }[priority] || '待处理'
    },
    studentMeta(student) {
      if (!student || typeof student !== 'object') return ''
      return [student.studentNo, student.className, student.majorName].filter(Boolean).join(' · ')
    },
    goWorkItem(item) {
      const action = item?.primaryAction || {}
      this.$router.push(this.routeWithBatch(action.path || '/admin/graduation', action.query || {}))
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
  grid-template-columns: minmax(300px, .95fr) minmax(0, 1.5fr);
  gap: var(--space-4);
  align-items: stretch;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: var(--radius-lg, 12px);
  color: #fff;
  background:
    radial-gradient(circle at 92% 10%, rgba(255, 255, 255, .16), transparent 26%),
    linear-gradient(120deg, var(--primary-900, #123a78), var(--primary-600, #2563eb));
  box-shadow: 0 16px 34px -24px rgba(37, 99, 235, .72);
}
.gdb-overview__conclusion { align-self: center; min-width: 0; }
.gdb-overview__eyebrow { display: block; margin-bottom: 6px; color: rgba(255, 255, 255, .72); font-size: var(--font-size-xs); font-weight: 700; letter-spacing: .08em; }
.gdb-overview__conclusion strong { display: block; font-size: 19px; line-height: 1.45; }
.gdb-overview__conclusion p { margin: 7px 0 0; color: rgba(255, 255, 255, .78); font-size: var(--font-size-xs); line-height: 1.6; }
.gdb-overview__context { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.gdb-overview__context span { max-width: 100%; padding: 4px 8px; overflow: hidden; border: 1px solid rgba(255, 255, 255, .18); border-radius: var(--radius-full); background: rgba(255, 255, 255, .08); color: rgba(255, 255, 255, .84); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.gdb-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.gdb-kpi { display: grid; align-content: center; min-width: 0; padding: 11px 12px; border: 1px solid rgba(255, 255, 255, .16); border-radius: var(--radius-md); background: rgba(255, 255, 255, .09); }
.gdb-kpi__value { display: block; font-size: 23px; font-weight: 700; line-height: 1.2; }
.gdb-kpi__label { display: block; margin-top: 4px; overflow: hidden; color: rgba(255, 255, 255, .88); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gdb-kpi__trend { display: block; margin-top: 2px; overflow: hidden; color: rgba(255, 255, 255, .64); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.gdb-work { overflow: hidden; border-color: var(--primary-100, #dbeafe); box-shadow: 0 14px 32px -28px rgba(37, 99, 235, .46); }
.gdb-work__head > div:first-child { display: grid; gap: 2px; }
.gdb-work__eyebrow { color: var(--primary-600, #2563eb); font-size: 11px; font-weight: 700; letter-spacing: .06em; }
.gdb-work__summary { display: grid; justify-items: end; gap: 1px; margin-left: auto; color: var(--text-secondary); font-size: var(--font-size-xs); }
.gdb-work__summary small { color: var(--text-tertiary); font-size: 11px; }
.gdb-work-list { display: grid; gap: 8px; }
.gdb-work-item { display: grid; grid-template-columns: 88px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); padding: 12px; border: 1px solid var(--border-light); border-left: 4px solid var(--primary-300, #93c5fd); border-radius: var(--radius-md); background: var(--card); }
.gdb-work-item.is-lead { border-color: var(--primary-200, #bfdbfe); border-left-color: var(--primary-600, #2563eb); box-shadow: 0 10px 24px -22px rgba(37, 99, 235, .7); }
.gdb-work-item.is-critical, .gdb-work-item.is-high { border-left-color: var(--danger-500, #ef4444); background: linear-gradient(90deg, var(--danger-50, #fef2f2), var(--card) 34%); }
.gdb-work-item.is-overdue, .gdb-work-item.is-due_24h, .gdb-work-item.is-release_blocker { border-left-color: var(--warning-500, #f59e0b); background: linear-gradient(90deg, var(--warning-50, #fffbeb), var(--card) 34%); }
.gdb-work-item__priority { display: grid; align-content: center; justify-items: start; gap: 3px; color: var(--text-secondary); font-size: var(--font-size-xs); font-weight: 700; }
.gdb-work-item__priority span { padding: 3px 7px; border-radius: var(--radius-full); background: var(--gray-100); white-space: nowrap; }
.gdb-work-item.is-critical .gdb-work-item__priority span, .gdb-work-item.is-high .gdb-work-item__priority span { color: var(--danger-700, #b91c1c); background: var(--danger-100, #fee2e2); }
.gdb-work-item.is-overdue .gdb-work-item__priority span, .gdb-work-item.is-due_24h .gdb-work-item__priority span, .gdb-work-item.is-release_blocker .gdb-work-item__priority span { color: var(--warning-800, #92400e); background: var(--warning-100, #fef3c7); }
.gdb-work-item__priority small { color: var(--primary-600, #2563eb); font-size: 10px; }
.gdb-work-item__main { min-width: 0; }
.gdb-work-item__identity { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; min-width: 0; }
.gdb-work-item__identity strong { overflow: hidden; color: var(--text-primary); text-overflow: ellipsis; white-space: nowrap; }
.gdb-work-item__identity > span { flex: none; color: var(--primary-700, #1d4ed8); font-size: var(--font-size-xs); font-weight: 700; }
.gdb-work-item__identity small { min-width: 0; overflow: hidden; color: var(--text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.gdb-work-item p { margin: 4px 0 7px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.5; }
.gdb-work-item__facts { display: flex; flex-wrap: wrap; gap: 5px 14px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gdb-work-item__facts span { display: inline-flex; min-width: 0; gap: 4px; }
.gdb-work-item__facts b { flex: none; color: var(--text-secondary); font-weight: 600; }
.gdb-work-item__action { justify-self: end; white-space: nowrap; }
.gdb-work-empty { display: flex; align-items: center; gap: var(--space-3); color: var(--text-secondary); }
.gdb-work-empty > span { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); font-weight: 700; }
.gdb-work-empty p { margin: 3px 0 0; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gdb-priority-grid { align-items: stretch; }
.gdb-priority-card, .gdb-risk-card { min-height: 0; }
.gdb-todos { display: grid; gap: 6px; }
.gdb-todo { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); width: 100%; padding: 8px 10px; border: 1px solid transparent; border-radius: var(--radius-md); background: transparent; color: inherit; text-align: left; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
.gdb-todo:hover { border-color: var(--border-light); background: var(--gray-50); }
.gdb-todo:focus-visible, .gdb-modstat:focus-visible, .gdb-risk-row:focus-visible, .gdb-work-item__action:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
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
.gdb-modstat:hover { border-color: var(--primary-200, #bfdbfe); background: var(--gray-50); }
.gdb-modstat__val { color: var(--primary-700, #1d4ed8); font-size: 18px; font-weight: 700; }
.gdb-modstat__label { margin-top: 2px; color: var(--text-primary); font-size: var(--font-size-xs); font-weight: 600; }
.gdb-modstat__hint { margin-top: 2px; overflow: hidden; color: var(--text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 1180px) {
  .gdb-overview { grid-template-columns: 1fr; }
  .gdb-kpis { grid-template-columns: repeat(5, minmax(110px, 1fr)); overflow-x: auto; }
  .gdb-flow { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .gdb-work__head { align-items: flex-start; }
  .gdb-work__summary { justify-items: start; width: 100%; margin-left: 0; }
  .gdb-work-item { grid-template-columns: 1fr; }
  .gdb-work-item__action { justify-self: start; }
  .gdb-priority-grid { grid-template-columns: 1fr; }
  .gdb-overview { padding: var(--space-3); }
  .gdb-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); overflow: visible; }
  .gdb-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gdb-modstats { grid-template-columns: 1fr; }
}
</style>
