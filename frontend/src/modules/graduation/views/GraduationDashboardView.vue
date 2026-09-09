<template>
  <ModulePageShell
    title="毕设总览"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions><ModuleToolbar :actions="toolbarActions" @action="onToolbar" /></template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="选择当前工作批次后，再查看真实待办、风险和阶段进度。"
    >
      <template #actions>
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/batches?panel=create')">＋ 新增毕设批次</button>
        <button class="mp-btn" @click="$router.push('/admin/graduation/batches?panel=list')">去批次列表</button>
      </template>
    </EmptyState>

    <div v-else class="mp-stack gdb-page">
      <section class="gdb-overview gdb-work" aria-label="当前最高优先工作">
        <div v-if="firstWorkItem" class="gdb-focus">
          <div class="gdb-focus__priority" :class="priorityClass(firstWorkItem.priority)">
            <span>{{ priorityLabel(firstWorkItem.priority) }}</span><small>现在先处理</small>
          </div>
          <div class="gdb-focus__main">
            <div class="gdb-focus__identity">
              <strong>{{ firstWorkItem.student?.name || firstWorkItem.business || '毕业设计事项' }}</strong>
              <span>{{ firstWorkItem.business || '毕业设计事项' }}</span>
              <small v-if="studentMeta(firstWorkItem.student)">{{ studentMeta(firstWorkItem.student) }}</small>
            </div>
            <p>{{ firstWorkItem.whyHere || '请进入任务查看当前情况。' }}</p>
            <div class="gdb-focus__facts">
              <span><b>当前等待</b>{{ firstWorkItem.waitingOn || '待确认' }}</span>
              <span><b>下一责任人</b>{{ firstWorkItem.nextActor || '待确认' }}</span>
              <span v-if="firstWorkItem.dueAt"><b>要求完成</b>{{ firstWorkItem.dueAt }}</span>
              <span><b>最近变化</b>{{ firstWorkItem.recentChange || '暂无新变化' }}</span>
            </div>
          </div>
          <button
            type="button"
            class="mp-btn mp-btn--primary gdb-focus__action"
            :aria-label="`${firstWorkItem.primaryAction?.label || '去处理'}：${firstWorkItem.student?.name || firstWorkItem.business || '毕业设计事项'}`"
            @click="goWorkItem(firstWorkItem)"
          >{{ firstWorkItem.primaryAction?.label || '去处理' }} →</button>
        </div>
        <div v-else class="gdb-focus gdb-focus--empty">
          <span class="gdb-focus__ok">✓</span>
          <div><strong>{{ priorityConclusion }}</strong><p>{{ priorityDetail }}</p></div>
        </div>

        <div class="gdb-kpis" aria-label="当前批次关键指标">
          <div v-for="s in keyStats" :key="s.label" class="gdb-kpi">
            <span>{{ s.label }}</span><strong>{{ s.value }}</strong><small v-if="s.trend">{{ s.trend }}</small>
          </div>
        </div>
      </section>

      <section v-if="remainingWorkItems.length" class="mp-card gdb-queue">
        <div class="mp-card__head">
          <span class="mp-card__title">后续工作</span>
          <small>共 {{ workItems.length }} 项 · 按服务端顺序</small>
        </div>
        <div class="mp-card__body gdb-queue__rows">
          <article v-for="(item, index) in remainingWorkItems" :key="workItemKey(item, index + 1)" class="gdb-work-row">
            <span class="gdb-work-row__priority" :class="priorityClass(item.priority)">{{ priorityLabel(item.priority) }}</span>
            <div>
              <strong>{{ item.student?.name || item.business || '毕业设计事项' }} · {{ item.business }}</strong>
              <p>{{ item.whyHere || item.recentChange || '查看当前任务详情' }}</p>
            </div>
            <button type="button" class="mp-link" @click="goWorkItem(item)">{{ item.primaryAction?.label || '处理' }} →</button>
          </article>
        </div>
      </section>

      <div class="mp-grid-2 gdb-action-grid">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">队列入口</span>
            <button class="mp-link" @click="goWithBatch('/admin/graduation/students')">全部学生 →</button>
          </div>
          <div class="mp-card__body gdb-todos">
            <button v-for="t in hero.todos" :key="t.id" class="gdb-todo" :class="'is-' + t.tone" type="button" @click="goTodo(t)">
              <b>{{ t.count }}</b>
              <span><strong>{{ t.label }}</strong><small>{{ t.hint }}</small></span>
              <i>进入 →</i>
            </button>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险提醒</span>
            <button class="mp-link" @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'risk' })">风险台账 →</button>
          </div>
          <div class="mp-card__body">
            <div v-if="!visibleRiskAlerts.length" class="gdb-risk-empty">
              <span>✓</span><div><strong>暂无新的风险提醒</strong><p>最高优先任务中已展示的风险不会在这里重复。</p></div>
            </div>
            <div v-else class="gdb-risks">
              <button v-for="r in visibleRiskAlerts" :key="r.id" class="gdb-risk-row" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'" type="button" @click="goRisk(r)">
                <span><strong>{{ r.code }} · {{ r.title }}</strong><small>{{ r.detail }}</small></span>
                <RiskTag :level="r.level" /><i>处置 →</i>
              </button>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card gdb-progress-card">
        <div class="mp-card__head">
          <span class="mp-card__title">批次进度</span>
          <span class="gdb-progress-card__meta">{{ hero.batchName || batchStore.selectedBatchName }} · {{ hero.batchStatus || batchStore.batchStatus || '—' }}</span>
        </div>
        <div class="mp-card__body gdb-flow">
          <div v-for="f in hero.flow" :key="f.label" class="gdb-flow__item" :class="{ 'is-active': f.active }">
            <strong>{{ f.value }}</strong><span>{{ f.label }}</span>
          </div>
        </div>
      </section>

      <details v-if="hero.moduleStats?.length" class="gdb-more">
        <summary>跨模块统计</summary>
        <div class="gdb-modstats">
          <button v-for="s in hero.moduleStats" :key="s.label" class="gdb-modstat" type="button" @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'stats' })">
            <strong>{{ s.value }}</strong><span>{{ s.label }}</span><small>{{ s.hint }}</small>
          </button>
        </div>
      </details>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const EMPTY_HERO = () => ({
  stats: [], flow: [], todos: [], todayWorkItems: [], riskAlerts: [], moduleStats: [],
  batchName: '', batchRange: '', batchStatus: ''
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
    return { batchStore: useGraduationBatchStore(), loading: true, error: '', hero: EMPTY_HERO() }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    pageSubtitle() {
      if (!this.hasBatch) return '请先选择或创建毕设批次'
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
      ].filter((action) => pa[action.key]?.visible).map((action) => ({
        ...action,
        disabled: !pa[action.key].allowed || (action.key !== 'createBatch' && action.key !== 'viewAuditLog' && !this.hasBatch),
        disabledReason: pa[action.key].reason
      }))
    },
    keyStats() { return (Array.isArray(this.hero.stats) ? this.hero.stats : []).slice(0, 5) },
    workItems() { return Array.isArray(this.hero.todayWorkItems) ? this.hero.todayWorkItems : [] },
    firstWorkItem() { return this.workItems[0] || null },
    remainingWorkItems() { return this.workItems.slice(1) },
    todoLoad() { return (this.hero.todos || []).reduce((sum, item) => sum + Math.max(0, Number(item.count) || 0), 0) },
    highRiskCount() {
      const stat = (this.hero.stats || []).find((item) => item.label === '高风险学生')
      return Math.max(0, Number(stat?.value) || 0)
    },
    priorityTodo() {
      return (this.hero.todos || []).filter((item) => Number(item.count) > 0).slice().sort((a, b) => Number(b.count) - Number(a.count))[0] || null
    },
    priorityConclusion() {
      if (!this.todoLoad && !this.highRiskCount) return '当前批次暂无待处理事项'
      if (this.highRiskCount) return `今日待办 ${this.todoLoad} 项，高风险 ${this.highRiskCount} 条`
      return this.priorityTodo ? `先处理「${this.priorityTodo.label}」` : `今日待办 ${this.todoLoad} 项`
    },
    priorityDetail() { return '继续关注队列、风险和阶段进度。' },
    visibleRiskAlerts() {
      const leadStudent = String(this.firstWorkItem?.student?.id || this.firstWorkItem?.student?.studentId || '')
      const leadText = `${this.firstWorkItem?.business || ''} ${this.firstWorkItem?.whyHere || ''}`
      return (this.hero.riskAlerts || []).filter((risk) => {
        const sameStudent = leadStudent && String(risk.gdStudentId || risk.studentId || '') === leadStudent
        const sameRiskText = /风险|预警/.test(leadText) && (leadText.includes(risk.title || '') || leadText.includes(risk.code || ''))
        return !(sameStudent && /风险|预警/.test(leadText)) && !sameRiskText
      }).slice(0, 4)
    }
  },
  created() { this.load() },
  watch: { 'batchStore.selectedBatchId'() { this.load() } },
  methods: {
    async load() {
      if (!this.batchStore.selectedBatchId) { this.loading = false; this.error = ''; this.hero = EMPTY_HERO(); return }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId })
        if (res.code === 0) this.hero = { ...EMPTY_HERO(), ...(res.data || {}) }
        else this.error = res.message || '毕业设计总览加载失败，请稍后重试。'
      } catch (error) { this.error = error?.message || '毕业设计总览加载失败，请检查网络后重试。' }
      finally { this.loading = false }
    },
    routeWithBatch(path, query = {}) {
      const [pathname, rawQuery = ''] = String(path || '').split('?')
      const inherited = Object.fromEntries(new URLSearchParams(rawQuery))
      const batchId = this.batchStore.selectedBatchId
      return { path: pathname, query: { ...inherited, ...query, ...(batchId ? { batchId: String(batchId) } : {}) } }
    },
    goWithBatch(path, query = {}) { this.$router.push(this.routeWithBatch(path, query)) },
    todoTarget(todo) {
      const target = TODO_TARGETS[todo?.id] || { path: todo?.route || '/admin/graduation', query: {} }
      return this.routeWithBatch(target.path, target.query)
    },
    goTodo(todo) { this.$router.push(this.todoTarget(todo)) },
    workItemKey(item, index) { return item?.id || `${item?.priority || 'NORMAL'}-${item?.student?.id || item?.student?.name || 'item'}-${index}` },
    priorityClass(priority) { return `is-${String(priority || 'NORMAL').toLowerCase()}` },
    priorityLabel(priority) {
      return { CRITICAL: '立即处理', HIGH: '高优先', OVERDUE: '已逾期', DUE_24H: '24 小时内', RELEASE_BLOCKER: '阻塞发布', RETURNED: '已退回', WAITING_REVIEW: '等待评阅', NORMAL: '常规' }[priority] || '待处理'
    },
    studentMeta(student) { return student && typeof student === 'object' ? [student.studentNo, student.className, student.majorName].filter(Boolean).join(' · ') : '' },
    goWorkItem(item) {
      const action = item?.primaryAction || {}
      this.$router.push(this.routeWithBatch(action.path || '/admin/graduation', action.query || {}))
    },
    goRisk(risk) { this.$router.push(this.routeWithBatch('/admin/graduation/risk-archive', { panel: 'risk', ...(risk?.id ? { rsel: String(risk.id) } : {}) })) },
    onToolbar(key) {
      if (key === 'createBatch') { this.$router.push('/admin/graduation/batches?panel=create'); return }
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
.gdb-page{gap:10px}.gdb-overview{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(420px,.8fr);gap:12px;align-items:stretch;padding:10px 12px;border:1px solid var(--primary-100);border-radius:11px;background:linear-gradient(110deg,#fff,var(--primary-50));box-shadow:0 10px 24px -24px rgba(37,99,235,.6)}.gdb-focus{display:grid;grid-template-columns:76px minmax(0,1fr) auto;align-items:center;gap:10px;min-width:0}.gdb-focus--empty{grid-template-columns:34px minmax(0,1fr)}.gdb-focus__ok{display:grid;width:32px;height:32px;place-items:center;border-radius:50%;background:var(--success-50);color:var(--success-700);font-weight:700}.gdb-focus__priority{display:grid;justify-items:start;gap:2px}.gdb-focus__priority span,.gdb-work-row__priority{padding:3px 6px;border-radius:999px;background:var(--gray-100);color:var(--text-secondary);font-size:9px;font-weight:700;white-space:nowrap}.gdb-focus__priority small{color:var(--primary-600);font-size:8px}.gdb-focus__priority.is-critical span,.gdb-focus__priority.is-high span,.gdb-work-row__priority.is-critical,.gdb-work-row__priority.is-high{background:var(--danger-100);color:var(--danger-700)}.gdb-focus__priority.is-overdue span,.gdb-focus__priority.is-due_24h span,.gdb-focus__priority.is-release_blocker span,.gdb-work-row__priority.is-overdue,.gdb-work-row__priority.is-due_24h,.gdb-work-row__priority.is-release_blocker{background:var(--warning-100);color:var(--warning-800)}.gdb-focus__main{min-width:0}.gdb-focus__identity{display:flex;align-items:baseline;flex-wrap:wrap;gap:3px 7px}.gdb-focus__identity strong{font-size:13px}.gdb-focus__identity span{color:var(--primary-700);font-size:10px;font-weight:700}.gdb-focus__identity small{color:var(--text-tertiary);font-size:9px}.gdb-focus__main>p,.gdb-focus--empty p{margin:2px 0 4px;color:var(--text-secondary);font-size:10px;line-height:1.4}.gdb-focus__facts{display:flex;gap:3px 10px;overflow:hidden;color:var(--text-tertiary);font-size:8px;white-space:nowrap}.gdb-focus__facts span{display:flex;gap:3px;min-width:0;overflow:hidden;text-overflow:ellipsis}.gdb-focus__facts b{flex:none;color:var(--text-secondary)}.gdb-focus__action{white-space:nowrap}.gdb-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));align-items:stretch}.gdb-kpi{display:grid;align-content:center;min-width:0;padding:3px 8px;border-left:1px solid var(--primary-100)}.gdb-kpi span,.gdb-kpi small{overflow:hidden;color:var(--text-tertiary);font-size:8px;text-overflow:ellipsis;white-space:nowrap}.gdb-kpi strong{font-size:17px}.gdb-queue .mp-card__head small{margin-left:auto;color:var(--text-tertiary);font-size:9px}.gdb-queue__rows{display:grid;gap:3px}.gdb-work-row{display:grid;grid-template-columns:72px minmax(0,1fr) auto;align-items:center;gap:8px;padding:5px 7px;border-bottom:1px solid var(--border-light)}.gdb-work-row:last-child{border-bottom:0}.gdb-work-row>div{min-width:0}.gdb-work-row strong,.gdb-work-row p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gdb-work-row strong{display:block;font-size:10px}.gdb-work-row p{margin:1px 0 0;color:var(--text-tertiary);font-size:9px}.gdb-action-grid{gap:10px;align-items:stretch}.gdb-todos,.gdb-risks{display:grid;gap:3px}.gdb-todo,.gdb-risk-row{display:grid;align-items:center;gap:7px;width:100%;padding:6px 7px;border:1px solid transparent;border-radius:8px;background:transparent;color:inherit;text-align:left;cursor:pointer}.gdb-todo{grid-template-columns:30px minmax(0,1fr) auto}.gdb-todo:hover,.gdb-risk-row:hover{border-color:var(--border-light);background:var(--gray-50)}.gdb-todo>b{display:grid;width:28px;height:28px;place-items:center;border-radius:50%;background:var(--primary-50);color:var(--primary-700);font-size:10px}.gdb-todo>span,.gdb-risk-row>span{display:grid;min-width:0;gap:1px}.gdb-todo strong,.gdb-risk-row strong{font-size:10px}.gdb-todo small,.gdb-risk-row small{overflow:hidden;color:var(--text-tertiary);font-size:8px;text-overflow:ellipsis;white-space:nowrap}.gdb-todo i,.gdb-risk-row i{color:var(--primary-600);font-size:9px;font-style:normal;white-space:nowrap}.gdb-risk-row{grid-template-columns:minmax(0,1fr) auto auto;border-left:3px solid var(--warning-400);background:var(--gray-50)}.gdb-risk-row.is-danger{border-left-color:var(--danger-400)}.gdb-risk-empty{display:flex;align-items:center;gap:9px;min-height:82px}.gdb-risk-empty>span{display:grid;width:30px;height:30px;place-items:center;border-radius:50%;background:var(--success-50);color:var(--success-700)}.gdb-risk-empty strong{font-size:10px}.gdb-risk-empty p{margin:2px 0 0;color:var(--text-tertiary);font-size:8px}.gdb-progress-card__meta{margin-left:auto;color:var(--text-tertiary);font-size:9px;font-weight:400}.gdb-flow{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:5px}.gdb-flow__item{display:grid;justify-items:center;gap:1px;padding:6px 3px;border-radius:7px;background:var(--gray-50)}.gdb-flow__item.is-active{background:var(--primary-50)}.gdb-flow__item strong{color:var(--primary-700);font-size:14px}.gdb-flow__item span{overflow:hidden;max-width:100%;color:var(--text-secondary);font-size:8px;text-overflow:ellipsis;white-space:nowrap}.gdb-more{padding:9px 11px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.gdb-more summary{cursor:pointer;font-size:10px;font-weight:700}.gdb-modstats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}.gdb-modstat{display:grid;gap:1px;padding:7px;border:1px solid var(--border-light);border-radius:7px;background:var(--gray-50);text-align:left}.gdb-modstat strong{color:var(--primary-700);font-size:14px}.gdb-modstat span{font-size:9px}.gdb-modstat small{color:var(--text-tertiary);font-size:8px}.mp-btn{padding:7px 13px;border:1px solid var(--border-base);border-radius:8px;background:#fff;font-size:11px}.mp-btn--primary{border-color:var(--primary-600);background:var(--primary-600);color:#fff}.mp-link{border:0;background:transparent;color:var(--primary-600);font-size:9px;cursor:pointer}
@media(max-width:1180px){.gdb-overview{grid-template-columns:1fr}.gdb-kpis{border-top:1px solid var(--primary-100);padding-top:7px}.gdb-kpi:first-child{border-left:0}.gdb-flow{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:850px){.gdb-focus{grid-template-columns:1fr}.gdb-focus__action{justify-self:start}.gdb-focus__facts{flex-wrap:wrap;white-space:normal}.gdb-action-grid{grid-template-columns:1fr}.gdb-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.gdb-kpi:nth-child(odd){border-left:0}.gdb-work-row{grid-template-columns:1fr}.gdb-flow{grid-template-columns:repeat(2,minmax(0,1fr))}.gdb-modstats{grid-template-columns:1fr}}
</style>
