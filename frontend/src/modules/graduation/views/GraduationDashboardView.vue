<template>
  <ModulePageShell
    class="gdb-shell"
    title="毕设总览"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #summary>
      <div class="gdb-kpis" aria-label="当前批次关键指标">
        <div v-for="s in keyStats" :key="s.label" class="gdb-kpi" :title="s.trend || s.label">
          <span>{{ s.label }}</span><strong>{{ s.value }}</strong>
        </div>
      </div>
    </template>
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
                <RiskTag :level="r.level" /><i>{{ r.actionLabel || '查看' }} →</i>
              </button>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card gdb-progress-card">
        <div class="mp-card__head">
          <span class="mp-card__title">批次进度</span>
          <span class="gdb-progress-card__meta">{{ hero.batchName || batchStore.selectedBatchName }} · {{ batchStatusLabel(hero.batchStatus || batchStore.batchStatus) }}</span>
        </div>
        <div class="mp-card__body gdb-flow">
          <div v-for="f in hero.flow" :key="f.label" class="gdb-flow__item" :class="{ 'is-active': f.active }">
            <strong>{{ f.value }}</strong><span>{{ f.label }}</span>
          </div>
        </div>
      </section>

      <details v-if="hasBatch" class="gdb-more" @toggle="onModuleStatsToggle">
        <summary>跨模块统计</summary>
        <p v-if="moduleStatsLoading" class="mp-note">正在读取跨模块统计…</p>
        <p v-else-if="moduleStatsError" class="mp-note">{{ moduleStatsError }}</p>
        <div v-else-if="moduleStats.length" class="gdb-modstats">
          <button v-for="s in moduleStats" :key="s.label" class="gdb-modstat" type="button" @click="goWithBatch('/admin/graduation/risk-archive', { panel: 'stats' })">
            <strong>{{ s.value }}</strong><span>{{ s.label }}</span><small>{{ s.hint }}</small>
          </button>
        </div>
        <p v-else class="mp-note">暂无可展示的跨模块统计。</p>
      </details>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationRiskArchiveApi } from '@/modules/graduation/api/graduation-risk-archive.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const EMPTY_HERO = () => ({
  stats: [], flow: [], todos: [], todayWorkItems: [], riskAlerts: [], moduleStats: [], actionableRiskCount: 0,
  batchName: '', batchRange: '', batchStatus: ''
})
const TODO_TARGETS = {
  t1: { path: '/admin/graduation/proposals', query: { tab: 'PENDING_REVIEW' } },
  t2: { path: '/admin/graduation/proposals', query: { tab: 'NOT_SUBMITTED' } },
  t3: { path: '/admin/graduation/finals', query: { tab: 'PENDING_REVIEW' } },
  t4: { path: '/admin/graduation/defense', query: {} },
  t5: { path: '/admin/graduation/risk-archive', query: { panel: 'risk' } }
}
function moduleStatsFromOverview(overview = {}) {
  const mentor = overview.mentor || {}
  const guidance = overview.guidance || {}
  const midterm = overview.midterm || {}
  const review = overview.review || {}
  const grade = overview.grade || {}
  const archive = overview.archive || {}
  const done = (stat, key) => (stat.byStatus || []).find((item) => item.status === key)?.count || 0
  return [
    { label: '导师已合格', value: String(mentor.qualifiedCount || 0), hint: `未分配学生 ${mentor.unassignedStudents || 0} · 满员 ${mentor.fullCapacityCount || 0}` },
    { label: '指导平均次数', value: String(guidance.avgCount || 0), hint: `频次不足 ${guidance.insufficientCount || 0} 人` },
    { label: '中期检查', value: String(midterm.total || 0), hint: `待检 ${done(midterm, 'PENDING')}` },
    { label: '教师评阅', value: String(review.total || 0), hint: `已完成 ${done(review, 'COMPLETED')}` },
    { label: '成绩已发布均分', value: String(grade.publishedAvg || '—'), hint: `优秀 ${grade.excellentCount || 0} 人` },
    { label: '归档率', value: `${archive.archiveRate || 0}%`, hint: `已备案 ${archive.filedCount || 0}/${archive.studentTotal || 0}` }
  ]
}

export default {
  name: 'GraduationDashboardView',
  components: { ModulePageShell, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(), loading: true, error: '', hero: EMPTY_HERO(),
      moduleStats: [], moduleStatsLoading: false, moduleStatsError: '', moduleStatsBatchId: '', moduleStatsLoadToken: 0
    }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    pageSubtitle() {
      if (!this.hasBatch) return '请先选择或创建毕设批次'
      const name = this.hero.batchName || this.batchStore.selectedBatchName || '当前批次'
      const status = this.hero.batchStatus || this.batchStore.batchStatus || ''
      return status ? `${name} · ${this.batchStatusLabel(status)}` : name
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
    actionableRiskCount() { return Math.max(0, Number(this.hero.actionableRiskCount) || 0) },
    priorityTodo() {
      return (this.hero.todos || []).filter((item) => Number(item.count) > 0).slice().sort((a, b) => Number(b.count) - Number(a.count))[0] || null
    },
    priorityConclusion() {
      if (!this.todoLoad && !this.actionableRiskCount) {
        return this.highRiskCount ? `当前范围有 ${this.highRiskCount} 条风险提醒` : '当前批次暂无待处理事项'
      }
      if (this.actionableRiskCount) return `今日待办 ${this.todoLoad} 项，高风险 ${this.highRiskCount} 条`
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
    batchStatusLabel(value) { return ({ DRAFT: '草稿', PREPARING: '准备中', RUNNING: '进行中', OPEN: '办理中', CLOSED: '已结束', ARCHIVED: '已归档', VOIDED: '已作废' }[value] || (value ? `状态待确认（${value}）` : '—')) },
    async load() {
      this.moduleStatsLoadToken += 1
      this.moduleStats = []
      this.moduleStatsLoading = false
      this.moduleStatsError = ''
      this.moduleStatsBatchId = ''
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
    onModuleStatsToggle(event) {
      if (event?.target?.open) this.loadModuleStats()
    },
    async loadModuleStats() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      if (!batchId || this.moduleStatsLoading || this.moduleStatsBatchId === batchId) return
      const token = this.moduleStatsLoadToken + 1
      this.moduleStatsLoadToken = token
      this.moduleStatsLoading = true
      this.moduleStatsError = ''
      try {
        const res = await graduationRiskArchiveApi.getOverviewStats({ batchId })
        if (token !== this.moduleStatsLoadToken || batchId !== String(this.batchStore.selectedBatchId || '')) return
        if (res.code !== 0) {
          this.moduleStatsError = res.message || '跨模块统计加载失败，请重新展开后重试。'
          return
        }
        this.moduleStats = moduleStatsFromOverview(res.data)
        this.moduleStatsBatchId = batchId
      } catch (error) {
        if (token === this.moduleStatsLoadToken) this.moduleStatsError = error?.message || '跨模块统计加载失败，请重新展开后重试。'
      } finally {
        if (token === this.moduleStatsLoadToken) this.moduleStatsLoading = false
      }
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
/* Content-only adaptation: the shared shell and all dashboard data stay upstream. */
.gdb-shell { container: gd-dashboard / inline-size; min-width: 0; }
.gdb-shell :deep(.mps__title) { font-size: 22px; line-height: 1.35; }
.gdb-shell :deep(.mps__subtitle) { font-size: 13px; }
.gdb-page { gap: 16px; font-size: 13px; line-height: 1.5; }
.gdb-overview {
  padding: 14px 16px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-left: 3px solid var(--pri, #2563eb);
  border-radius: 12px;
  background: var(--card, #fff);
  color: var(--text-primary, #10233f);
}
.gdb-focus { display: grid; grid-template-columns: 88px minmax(0, 1fr) auto; align-items: center; gap: 12px; min-width: 0; }
.gdb-focus--empty { grid-template-columns: 36px minmax(0, 1fr); }
.gdb-focus__ok, .gdb-risk-empty > span { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--success-50, #f0fdf4); color: var(--success-700, #15803d); font-weight: 700; }
.gdb-focus__priority { display: grid; justify-items: start; gap: 6px; }
.gdb-focus__priority span, .gdb-work-row__priority { padding: 4px 8px; border-radius: 8px; background: var(--bg-hover, #eef3f9); color: var(--text-secondary, #3f5878); font-size: 12px; font-weight: 700; white-space: nowrap; }
.gdb-focus__priority small { color: var(--pri, #2563eb); font-size: 11px; }
.gdb-focus__priority.is-critical span, .gdb-focus__priority.is-high span, .gdb-work-row__priority.is-critical, .gdb-work-row__priority.is-high { background: var(--danger-100, #fee2e2); color: var(--danger-700, #b91c1c); }
.gdb-focus__priority.is-overdue span, .gdb-focus__priority.is-due_24h span, .gdb-focus__priority.is-release_blocker span,
.gdb-work-row__priority.is-overdue, .gdb-work-row__priority.is-due_24h, .gdb-work-row__priority.is-release_blocker { background: var(--warning-100, #fef3c7); color: var(--warning-800, #92400e); }
.gdb-focus__main { min-width: 0; }
.gdb-focus__identity { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; }
.gdb-focus__identity strong, .gdb-focus--empty strong { font-size: 16px; font-weight: 700; }
.gdb-focus__identity span { color: var(--pri, #2563eb); font-size: 13px; font-weight: 600; }
.gdb-focus__identity small { color: var(--text-tertiary, #75879d); font-size: 12px; }
.gdb-focus__main > p, .gdb-focus--empty p { margin: 4px 0 6px; color: var(--text-secondary, #3f5878); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.gdb-focus__facts { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--text-secondary, #3f5878); font-size: 12px; }
.gdb-focus__facts span { min-width: 0; overflow-wrap: anywhere; }
.gdb-focus__facts b { margin-right: 6px; color: var(--text-tertiary, #75879d); font-weight: 500; }
.gdb-focus__action { white-space: nowrap; }
.gdb-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.gdb-kpi { display: grid; align-content: start; gap: 4px; min-width: 0; padding: 10px 14px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--card, #fff); }
.gdb-kpi span, .gdb-kpi small { color: var(--text-tertiary, #75879d); font-size: 12px; overflow-wrap: anywhere; }
.gdb-kpi strong { font-size: 24px; line-height: 1.15; font-variant-numeric: tabular-nums; color: var(--text-primary, #10233f); }
.gdb-page .mp-card { border: 1px solid var(--border-light, #dce6f1); border-radius: 12px; background: var(--card, #fff); box-shadow: none; }
.gdb-page .mp-card__head { flex-wrap: wrap; gap: 8px; min-height: 48px; padding: 10px 14px; }
.gdb-page .mp-card__title { font-size: 16px; font-weight: 650; }
.gdb-page .mp-card__body { padding: 12px 14px; }
.gdb-queue .mp-card__head small { margin-left: auto; color: var(--text-tertiary, #75879d); font-size: 12px; }
.gdb-queue__rows { display: grid; }
.gdb-work-row { display: grid; grid-template-columns: 88px minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-light, #dce6f1); }
.gdb-work-row:first-child { padding-top: 0; }
.gdb-work-row:last-child { padding-bottom: 0; border-bottom: 0; }
.gdb-work-row > div { min-width: 0; }
.gdb-work-row__priority { justify-self: start; }
.gdb-work-row strong { display: block; font-size: 14px; overflow-wrap: anywhere; }
.gdb-work-row p { margin: 4px 0 0; color: var(--text-tertiary, #75879d); font-size: 12px; overflow-wrap: anywhere; }
.gdb-action-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: stretch; }
.gdb-todos, .gdb-risks { display: grid; gap: 8px; }
.gdb-todo, .gdb-risk-row { display: grid; align-items: center; gap: 10px; width: 100%; min-height: 64px; padding: 10px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--bg-subtle, #f8fafc); color: inherit; text-align: left; cursor: pointer; }
.gdb-todo { grid-template-columns: 40px minmax(0, 1fr) auto; }
.gdb-todo:hover, .gdb-risk-row:hover { border-color: var(--pri, #2563eb); background: var(--bg-hover, #eff6ff); }
.gdb-todo > b { display: grid; min-width: 36px; min-height: 36px; padding: 2px; place-items: center; border-radius: 10px; background: var(--pri-bg, #eff6ff); color: var(--pri, #2563eb); font-size: 18px; font-variant-numeric: tabular-nums; }
.gdb-todo > span, .gdb-risk-row > span { display: grid; min-width: 0; gap: 4px; }
.gdb-todo strong, .gdb-risk-row strong { font-size: 13px; overflow-wrap: anywhere; }
.gdb-todo small, .gdb-risk-row small { color: var(--text-tertiary, #75879d); font-size: 12px; white-space: normal; overflow-wrap: anywhere; }
.gdb-todo i, .gdb-risk-row i { color: var(--pri, #2563eb); font-size: 13px; font-style: normal; white-space: nowrap; }
.gdb-risk-row { grid-template-columns: minmax(0, 1fr) auto auto; border-left: 3px solid var(--warning-400, #fbbf24); }
.gdb-risk-row.is-danger { border-left-color: var(--danger-400, #f87171); }
.gdb-risk-empty { display: flex; align-items: center; gap: 12px; min-height: 82px; }
.gdb-risk-empty > span { flex-shrink: 0; }
.gdb-risk-empty strong { font-size: 14px; }
.gdb-risk-empty p { margin: 4px 0 0; color: var(--text-tertiary, #75879d); font-size: 12px; }
.gdb-progress-card__meta { margin-left: auto; color: var(--text-tertiary, #75879d); font-size: 12px; font-weight: 400; overflow-wrap: anywhere; }
.gdb-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(105px, 1fr)); gap: 10px; }
.gdb-flow__item { display: grid; justify-items: center; gap: 6px; padding: 12px 8px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--bg-subtle, #f8fafc); }
.gdb-flow__item.is-active { border-color: var(--pri, #2563eb); background: var(--pri-bg, #eff6ff); }
.gdb-flow__item strong { color: var(--pri, #2563eb); font-size: 20px; font-variant-numeric: tabular-nums; }
.gdb-flow__item span { max-width: 100%; color: var(--text-secondary, #3f5878); font-size: 12px; overflow-wrap: anywhere; }
.gdb-more { padding: 10px 14px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--card, #fff); }
.gdb-more summary { min-height: 34px; align-content: center; cursor: pointer; font-size: 13px; font-weight: 600; }
.gdb-modstats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }
.gdb-modstat { display: grid; gap: 4px; min-width: 0; padding: 12px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--bg-subtle, #f8fafc); color: var(--text-primary, #10233f); text-align: left; }
.gdb-modstat strong { color: var(--pri, #2563eb); font-size: 20px; }
.gdb-modstat span { font-size: 13px; }
.gdb-modstat small { color: var(--text-tertiary, #75879d); font-size: 12px; overflow-wrap: anywhere; }
.mp-btn { min-height: 36px; padding: 7px 13px; border: 1px solid var(--border-base, #cbd8e8); border-radius: 8px; background: var(--card, #fff); color: var(--text-primary, #10233f); font-size: 13px; cursor: pointer; }
.mp-btn--primary { border-color: var(--pri, #2563eb); background: var(--pri, #2563eb); color: var(--pri-on, #fff); }
.mp-link { min-height: 34px; padding: 6px 8px; border: 0; border-radius: 7px; background: transparent; color: var(--pri, #2563eb); font-size: 13px; cursor: pointer; }
.gdb-page button:focus-visible, .gdb-page summary:focus-visible { outline: 2px solid var(--pri, #2563eb); outline-offset: 2px; }
@container gd-dashboard (max-width: 900px) {
  .gdb-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .gdb-action-grid { grid-template-columns: 1fr; }
}
@container gd-dashboard (max-width: 600px) {
  .gdb-focus { grid-template-columns: 1fr; }
  .gdb-focus__priority { display: flex; align-items: center; gap: 8px; }
  .gdb-focus__action { grid-column: 1; }
  .gdb-focus--empty { grid-template-columns: 36px minmax(0, 1fr); }
  .gdb-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gdb-work-row { grid-template-columns: minmax(0, 1fr) auto; }
  .gdb-work-row__priority { grid-column: 1 / -1; }
  .gdb-modstats { grid-template-columns: 1fr; }
}
@supports not (container-type: inline-size) {
  @media (max-width: 1100px) {
    .gdb-focus { grid-template-columns: 1fr; }
    .gdb-focus__action { justify-self: start; }
    .gdb-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .gdb-action-grid, .gdb-modstats { grid-template-columns: 1fr; }
  }
}
</style>
