<template>
  <AaOverviewPageFrame class="academic-overview" :title="mode === 'todos' ? '教务待办' : '运行总览'" :subtitle="mode === 'todos' ? '区分待我启动、待我办理、我发起和已办' : '把今天应启动和应办理的工作放在一起'">
    <template #actions><AppButton v-if="mode === 'overview'" @click="openWall">查看运行大屏</AppButton><AppButton v-else @click="$router.push('/admin/academic-affairs')">返回运行总览</AppButton><AppButton variant="primary" :loading="loading" @click="loadQueue">更新责任队列</AppButton></template>
    <p v-if="message" class="overview-message" role="status">{{ message }}</p>
    <div class="overview-metrics">
      <article v-for="metric in metrics" :key="metric.key" :class="{ 'is-due': metric.key === 'nearDeadline' }"><span>{{ metric.label }}</span><strong>{{ countLabel(queue.summary?.[metric.key]) }}</strong><small>{{ metric.note }}</small></article>
    </div>
    <nav class="overview-tabs" aria-label="责任队列"><button v-for="item in tabs" :key="item.key" :aria-pressed="tab === item.key" @click="selectTab(item.key)">{{ item.label }}</button></nav>
    <div class="overview-columns">
      <section class="overview-queue">
        <header><h2>{{ currentTab.label }}</h2><span>{{ queue.sourceTime ? sourceTimeLabel(queue.sourceTime) + '更新' : '等待读取正式待办' }}</span></header>
        <form class="overview-search" @submit.prevent="search"><input v-model="keyword" maxlength="100" aria-label="搜索教务事项" :placeholder="mode === 'todos' ? '搜索岗位待办' : '搜索本学期教务任务'" :disabled="unsupported" /><AppButton :disabled="unsupported" @click="search">查询</AppButton><AppButton variant="ghost" :disabled="unsupported" @click="clearSearch">清空</AppButton><small>{{ unsupported ? '当前分类暂未接入' : `共 ${queue.total ?? '—'} 条 · 按当前身份查询` }}</small></form>
        <LoadingState v-if="loading" />
        <ErrorState v-else-if="error" :description="error" @retry="loadQueue" />
        <EmptyState v-else-if="queue.scopeBlocked" title="当前身份尚未确认" description="请重新确认当前账号和角色后读取正式责任队列。" />
        <EmptyState v-else-if="unsupported" :title="currentTab.label + '暂未接入'" description="此分类暂无正式统计来源，请进入右侧责任工作区核对。" />
        <EmptyState v-else-if="!rows.length" :title="currentTab.label + '暂无记录'" description="当前身份及查询条件下暂无正式待办，可调整查询条件。" />
        <template v-else>
          <DataTable :columns="columns" :rows="rows" row-key="todoId" :pagination="pagination" @page-change="changePage">
            <template #cell-title="{ row }"><strong class="overview-title" :title="row.title">{{ row.title }}</strong><small class="overview-secondary">待办 {{ row.todoId }} · {{ statusLabel(row.status) }}</small></template>
            <template #cell-object="{ row }"><span>{{ objectLabel(row.sourceBizType) }}</span><small class="overview-secondary">{{ row.sourceBizId || '对象编号未提供' }}</small></template>
            <template #cell-responsibility="{ row }"><span :title="row.assignmentReason">{{ row.responsibility }}</span></template>
            <template #cell-deadline="{ row }">{{ dateLabel(row.dueAt) }}</template>
            <template #cell-blocker="{ row }">{{ row.blocker || (mode === 'todos' ? '进入原业务核对下一责任' : '进入原业务核对') }}</template>
            <template #cell-action="{ row }"><button v-if="canOpenTodo(row)" class="overview-link" @click="openTodo(row)">{{ row.routeExact ? '继续办理' : '前往责任列表' }}</button><span v-else class="overview-secondary">暂无可用办理入口</span></template>
          </DataTable>
        </template>
      </section>
      <aside class="overview-aside">
        <section class="overview-relay"><h2>本学期业务接力</h2><ol><li v-for="step in relay" :key="step.title"><h3>{{ step.title }}</h3><p>{{ step.description }}</p><button v-if="canOpen(step.target)" @click="go(step.target)">进入责任工作区</button><span v-else>当前角色无入口权限</span></li></ol></section>
        <p class="overview-scope-card"><strong>按当前身份呈现责任</strong>待办来自正式指派和授权责任池。学院、教师与校级身份不共用一组全校统计。</p>
      </aside>
    </div>
    <section v-if="mode === 'overview'" class="overview-readiness">
      <header><div><h2>学期运行检查</h2><p>按所选学期核对运行前置条件，检查结果不代替业务审批。</p></div><AppTermEntityPicker v-model="termId" placeholder="当前学期" @change="changeTerm" /><AppButton :loading="readinessLoading" @click="loadReadiness">更新检查</AppButton></header>
      <LoadingState v-if="readinessLoading" /><ErrorState v-else-if="readinessError" :description="readinessError" @retry="loadReadiness" />
      <template v-else>
        <div class="readiness-conclusion"><strong>{{ readiness.stageLabel || '运行阶段待核对' }} · {{ readinessStatus }}</strong><p>{{ readiness.conclusion || '运行结论尚未提供' }}</p><span>阻断 {{ countLabel(readiness.blockerCount) }} 项 · 风险 {{ countLabel(readiness.riskCount) }} 项</span></div>
        <details><summary>查看 {{ readinessItems.length }} 条规则明细及责任</summary><div class="readiness-items"><article v-for="(item, index) in readinessItems" :key="item.key || index"><div><strong>{{ safeBusinessMessage(item.title, '运行检查事项') }}</strong><p>{{ safeBusinessMessage(item.summary, '请进入责任页面核对') }}</p><small>{{ item.ownerRole || '责任岗位待明确' }} · {{ item.deadlineLabel || item.deadline || '截止时间未提供' }}</small></div><AppButton v-if="canOpen(item.route)" @click="go(item.route)">查看责任对象</AppButton></article></div></details>
        <form class="readiness-export" @submit.prevent="exportChecklist"><input v-model.trim="purpose" maxlength="80" aria-label="运行检查导出用途" placeholder="导出用途（不少于5字）" /><AppButton @click="exportChecklist" :loading="exporting" :disabled="!readiness.term?.termId || purpose.length < 5">导出运行检查</AppButton></form>
      </template>
    </section>
  </AaOverviewPageFrame>
</template>

<script>
import { DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker } from '@/components/common'
import { request, currentUserFromToken } from '@/services/http/client'
import { academicAffairsApi } from '../api/academic-affairs.api'
import { academicAffairsDashboardReadinessApi as readinessApi } from '../api/academic-affairs-dashboard-readiness.api'
import { academicIdentity, createAcademicReturnStore } from '../academicFlowContext'
import { adaptTypedTodoPage } from '@/modules/workbench/config/todoTypedRouteBridge'
import { canEnterRoute } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'
import { routeTarget } from './leadershipWall/aa-wall-data.mjs'
import { routeAllowed } from './leadershipWall/aa-wall-runtime.mjs'
import { sourceTimeLabel } from './leadershipWall/aa-wall-presentation.mjs'
import { safeBusinessMessage } from '@/utils/presentationSafety'

import AaOverviewPageFrame from './AaOverviewPageFrame.vue'

const TABS = [{ key: 'pending', label: '待我办理' }, { key: 'toStart', label: '待我启动' }, { key: 'initiated', label: '我发起的' }, { key: 'done', label: '我的已办' }]
const METRICS = [{ key: 'toStart', label: '待我启动', note: '须由正式启动条件认定' }, { key: 'pending', label: '待我办理', note: '本人指派及授权责任池' }, { key: 'initiated', label: '我发起的', note: '须有正式发起人记录' }, { key: 'nearDeadline', label: '即将到期', note: '未来24小时内到期的待办' }]
export default {
  name: 'AaOverviewWorkspace',
  components: { AaOverviewPageFrame, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppTermEntityPicker },
  props: { ctx: { type: Object, required: true }, mode: { type: String, default: 'overview' } },
  data() { return {
    loading: false, error: '', queue: {}, keyword: '', message: '', requestId: 0, disposed: false,
    termId: '', readiness: {}, readinessError: '', readinessLoading: false, readinessId: 0,
    purpose: '', exporting: false, exportId: 0, tabs: TABS, metrics: METRICS,
    overviewColumns: [{ key: 'title', title: '事项' }, { key: 'object', title: '业务对象' }, { key: 'responsibility', title: '当前责任' }, { key: 'deadline', title: '截止时间' }, { key: 'blocker', title: '阻断原因' }, { key: 'action', title: '办理入口' }],
    relay: [{ title: '开学条件', description: '校历、组织与注册', target: 'aa-registration' }, { title: '开课与课表', description: '任务、名单与正式课位', target: 'aa-teaching-tasks' }, { title: '考试与成绩', description: '岗位审核与实际回执', target: 'aa-grade-overview' }, { title: '毕业与归档', description: '证据核验与受控封存', target: 'aa-archive' }]
  } },
  computed: {
    columns() { return this.mode === 'todos' ? [{ key: 'title', title: '任务' }, { key: 'object', title: '来源对象' }, { key: 'responsibility', title: '责任岗位' }, { key: 'deadline', title: '截止时间' }, { key: 'blocker', title: '下一步' }, { key: 'action', title: '办理入口' }] : this.overviewColumns },
    tab() { return TABS.some(item => item.key === this.$route.query.tab) ? this.$route.query.tab : 'pending' },
    currentTab() { return TABS.find(item => item.key === this.tab) },
    unsupported() { return ['toStart', 'initiated'].includes(this.tab) },
    page() { const value = Number(this.$route.query.page); return Number.isSafeInteger(value) && value > 0 && value <= 1000000 ? value : 1 },
    pageSize() { const value = Number(this.$route.query.pageSize); return [5, 10, 20, 50, 100].includes(value) ? value : 5 },
    rows() { return Array.isArray(this.queue.items) ? this.queue.items : [] },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.queue.total ?? 0 } },
    contextSignature() { return JSON.stringify([this.ctx.ctxKey, this.ctx.permissionPatterns, this.ctx.dataScope, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    readinessItems() { return Array.isArray(this.readiness.items) ? this.readiness.items : [] },
    readinessStatus() { return ({ NORMAL: '可继续', RISK: '存在风险', BLOCKED: '存在阻断' })[this.readiness.status] || '状态待核对' }
  },
  created() { this.syncRoute(); this.loadQueue(); if (this.mode === 'overview') this.loadReadiness() },
  beforeUnmount() { this.disposed = true; this.invalidate() },
  watch: {
    '$route.fullPath'() { this.syncRoute(); this.loadQueue() },
    '$route.query.termId'() { this.syncRoute(); this.exportId++; this.exporting = false; this.loadReadiness() },
    contextSignature() { this.invalidate(); this.queue = {}; this.readiness = {}; this.purpose = ''; this.message = ''; this.loadQueue(); this.loadReadiness() }
  },
  methods: {
    safeBusinessMessage, sourceTimeLabel,
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    invalidate() { this.requestId++; this.readinessId++; this.exportId++; this.exporting = false },
    current(id, identity, key) { return !this.disposed && id === this[key] && identity === this.identity() },
    countLabel(value) { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : '—' },
    statusLabel(value) { return ({ PENDING: '待办理', DONE: '已完成', CANCELLED: '已取消' })[value] || '状态待核对' },
    objectLabel(value) { return ({ AA_GRADE_TASK: '成绩任务', AA_STATUS_CHANGE: '学籍异动', AA_SCHEDULE_CHANGE: '调停课申请', AA_REGISTRATION: '注册记录', AA_WARNING: '学业预警', AA_GRADUATION: '毕业审核' })[value] || '教务业务对象' },
    dateLabel(value) { return value ? sourceTimeLabel(value) : '未设置截止时间' },
    syncRoute() { this.keyword = typeof this.$route.query.keyword === 'string' ? this.$route.query.keyword.slice(0, 100) : ''; this.termId = typeof this.$route.query.termId === 'string' ? this.$route.query.termId : '' },
    routeQuery(changes) { return { ...this.$route.query, ...changes } },
    selectTab(tab) { this.$router.push({ path: this.$route.path, query: this.routeQuery({ tab, page: '1' }) }) },
    changePage(page) { this.$router.push({ path: this.$route.path, query: this.routeQuery({ page: String(page) }) }) },
    search() {
      const keyword = this.keyword.trim()
      if (keyword === (this.$route.query.keyword || '') && this.page === 1) this.loadQueue()
      else this.$router.push({ path: this.$route.path, query: this.routeQuery({ keyword: keyword || undefined, page: '1' }) })
    },
    clearSearch() { this.keyword = ''; this.search() },
    changeTerm() { this.$router.replace({ path: this.$route.path, query: this.routeQuery({ termId: this.termId ? String(this.termId) : undefined }) }) },
    async loadQueue() {
      const id = ++this.requestId, identity = this.identity()
      this.loading = true; this.error = ''; this.queue = {}
      try {
        const response = await academicAffairsApi.getDashboardRoleQueue({ status: this.tab === 'done' ? 'DONE' : 'PENDING', keyword: typeof this.$route.query.keyword === 'string' ? this.$route.query.keyword : '', page: this.page, pageSize: this.pageSize })
        if (!this.current(id, identity, 'requestId')) return
        if (response.code !== 0 || !Array.isArray(response.data?.items) || !Number.isSafeInteger(response.data.total)) throw new Error(response.message || '正式责任队列读取失败')
        this.queue = adaptTypedTodoPage(response.data)
      } catch (error) { if (this.current(id, identity, 'requestId')) { this.queue = {}; this.error = safeBusinessMessage(error?.message, '责任队列读取失败，请重试') } }
      finally { if (this.current(id, identity, 'requestId')) this.loading = false }
    },
    async loadReadiness() {
      if (this.mode !== 'overview') return
      const id = ++this.readinessId, identity = this.identity(), term = String(this.termId || '')
      this.readinessLoading = true; this.readinessError = ''; this.readiness = {}
      try {
        const data = await readinessApi.get(term || undefined)
        if (!this.current(id, identity, 'readinessId') || term !== String(this.termId || '')) return
        if (!data || !Array.isArray(data.items) || (term && String(data.term?.termId) !== term)) throw new Error('运行检查返回的学期或规则不匹配，请重新读取')
        this.readiness = data
      } catch (error) { if (this.current(id, identity, 'readinessId')) this.readinessError = safeBusinessMessage(error?.message, '运行检查读取失败') }
      finally { if (this.current(id, identity, 'readinessId')) this.readinessLoading = false }
    },
    target(target) {
      const location = typeof target === 'string' ? routeTarget(target) : null
      if (!location?.path) return location
      // Vue Router parses embedded query/hash from a string, not from an object's path.
      const resolved = this.$router.resolve(location.path)
      return { path: resolved.path, query: resolved.query, hash: resolved.hash }
    },
    canOpen(target) {
      const location = this.target(target); if (!location) return false
      try { const resolved = this.$router.resolve(location); return !!resolved.matched?.length && resolved.matched.every(row => canEnterRoute(row.meta)) } catch { return false }
    },
    canOpenTodo(row) { return row.allowedActions?.includes('OPEN') && this.canOpen(row.typedRouteTarget) },
    openTodo(row) { if (this.canOpenTodo(row)) this.go(row.typedRouteTarget) },
    async go(target) {
      if (!this.canOpen(target)) return
      const identity = this.identity()
      this.message = ''
      try {
        const context = await request('/rbac/current-context')
        if (this.disposed || identity !== this.identity()) return
        const location = this.target(target), resolved = this.$router.resolve(location)
        const can = (scope, code) => scope?.rbacOk !== false && Array.isArray(scope?.permissionPatterns) && matchPermission(scope.permissionPatterns, code)
        if (!routeAllowed(resolved, context, can)) { this.message = '当前身份无法进入该责任页面。'; return }
        let returnToken = ''
        try { returnToken = createAcademicReturnStore(window.sessionStorage).remember(this.$route, identity, this.$el.closest('.tw-main')?.scrollTop || 0) } catch { /* Native browser Back retains the queue URL when storage is unavailable. */ }
        await this.$router.push({ path: resolved.path, query: { ...resolved.query, ...(returnToken ? { returnToken } : {}) }, hash: resolved.hash })
      } catch (error) { if (!this.disposed && identity === this.identity()) this.message = safeBusinessMessage(error?.message, '无法进入责任工作区，请重试') }
    },
    openWall() { this.$router.push({ path: this.$route.path, query: this.routeQuery({ wall: '1' }) }) },
    async exportChecklist() {
      if (this.exporting || this.purpose.length < 5 || !this.readiness.term?.termId) return
      const id = ++this.exportId, identity = this.identity(), selected = String(this.termId || ''), term = String(this.readiness.term.termId), name = this.readiness.term.termCode || '学期'
      this.exporting = true; this.message = ''
      try {
        const blob = await readinessApi.exportXlsx(term, this.purpose)
        if (!this.current(id, identity, 'exportId') || selected !== String(this.termId || '') || term !== String(this.readiness.term?.termId)) return
        const url = URL.createObjectURL(blob), link = document.createElement('a')
        try { link.href = url; link.download = name + '-教务运行准备清单.xlsx'; document.body.appendChild(link); link.click(); this.message = '运行检查已导出。' } finally { link.remove(); URL.revokeObjectURL(url) }
      } catch (error) { if (this.current(id, identity, 'exportId')) this.message = safeBusinessMessage(error?.message, '运行检查导出失败') }
      finally { if (this.current(id, identity, 'exportId')) this.exporting = false }
    }
  }
}
</script>

<style scoped>
.overview-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }.overview-metrics article { padding:16px; display:grid; gap:10px; background:var(--bg-card); border:1px solid var(--border-base); border-radius:11px; }.overview-metrics span,.overview-metrics small { color:var(--text-secondary); font-size:12px; line-height:1.6; }.overview-metrics strong { font-size:27px; font-variant-numeric:tabular-nums; }.overview-metrics .is-due { background:var(--warning-bg,#fff6e5); border-color:var(--warning-border,#e7d8b9); }.is-due strong { color:var(--warning-text,#97600c); }
.overview-tabs { display:flex; gap:5px; flex-wrap:wrap; }.overview-tabs button { padding:9px 12px; border:0; border-radius:7px; color:var(--text-secondary); background:transparent; font:inherit; font-size:13px; cursor:pointer; }.overview-tabs button[aria-pressed=true] { background:var(--pri-bg,#e6edff); color:var(--pri,#2c5ca8); font-weight:650; }
.overview-columns { display:grid; grid-template-columns:minmax(0,1fr) 280px; gap:16px; align-items:start; }.overview-queue,.overview-relay,.overview-readiness { border:1px solid var(--border-base); border-radius:11px; background:var(--bg-card); overflow:hidden; }.overview-queue > header,.overview-readiness > header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; padding:16px; border-bottom:1px solid var(--border-base); }.overview-queue h2,.overview-relay h2,.overview-readiness h2 { margin:0; font-size:15px; }.overview-queue header > span { color:var(--text-secondary); font-size:11px; }.overview-search,.readiness-export { display:flex; align-items:center; gap:8px; padding:14px 16px; flex-wrap:wrap; }.overview-search input,.readiness-export input { min-width:160px; max-width:300px; flex:1; height:36px; padding:0 10px; border:1px solid var(--border-base); border-radius:7px; font:inherit; font-size:13px; background:var(--bg-card); color:var(--text-primary); }.overview-scope { padding:0 16px; font-size:12px; color:var(--text-secondary); line-height:1.7; }.overview-title { color:var(--pri,#2c5ca8); font-size:13px; }.overview-secondary { display:block; font-size:11px; line-height:1.7; color:var(--text-secondary); margin-top:4px; }
.overview-relay h2 { padding:16px; border-bottom:1px solid var(--border-base); }.overview-relay ol { list-style:none; margin:0 16px; padding:0 0 0 11px; border-left:1px solid var(--border-base); }.overview-relay li { position:relative; padding:14px 0 8px; }.overview-relay li::before { content:''; position:absolute; left:-15px; top:21px; width:7px; height:7px; border-radius:50%; background:var(--pri,#2c5ca8); }.overview-relay h3 { font-size:13px; margin:0 0 6px; }.overview-relay p,.overview-relay li > span { color:var(--text-secondary); font-size:12px; line-height:1.6; margin:0; }.overview-relay button { padding:2px 0 0; border:0; color:var(--pri,#2c5ca8); background:transparent; cursor:pointer; font:inherit; font-size:13px; }.overview-scope-card { padding:16px; border-radius:10px; background:var(--pri-bg,#e7edfc); color:var(--pri,#2c5ca8); line-height:1.7; font-size:12px; }.overview-scope-card strong { display:block; margin-bottom:5px; }
.overview-readiness > header > div { flex:1; }.overview-readiness header p { font-size:12px; color:var(--text-secondary); margin:6px 0 0; }.readiness-conclusion { padding:16px; }.readiness-conclusion strong { font-size:15px; }.readiness-conclusion p,.readiness-conclusion span { font-size:13px; color:var(--text-secondary); line-height:1.7; }.overview-readiness details { padding:0 16px 16px; }.overview-readiness summary { font-size:13px; cursor:pointer; color:var(--pri,#2c5ca8); }.readiness-items article { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:16px 0; border-bottom:1px solid var(--border-base); }.readiness-items strong { font-size:13px; }.readiness-items p,.readiness-items small { color:var(--text-secondary); line-height:1.7; font-size:12px; margin:5px 0; }.readiness-export { border-top:1px solid var(--border-base); }.overview-message { padding:12px 16px; font-size:13px; background:var(--warning-bg,#fff6e5); border-radius:8px; }
.academic-overview :is(button,input):focus-visible { outline:2px solid var(--pri,#2c5ca8); outline-offset:2px; }
@container academic-body (max-width:740px) { .overview-columns { grid-template-columns:minmax(0,1fr); }.overview-aside { display:grid; grid-template-columns:1fr 1fr; gap:16px; }.overview-scope-card { margin:0; } }
@container academic-body (max-width:580px) { .overview-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }.overview-aside { grid-template-columns:1fr; } }
.academic-overview .overview-search small { margin-left:auto; font-size:12px; color:var(--text-secondary); }
.academic-overview .overview-relay li { padding:12px 0 8px; }
.academic-overview .overview-scope-card { margin:14px 0 0; }
.academic-overview .overview-queue :deep(.dt) { border:0; border-radius:0; }
.academic-overview .overview-queue :deep(.dt__scroll) { border-radius:0; }
.academic-overview .overview-queue :deep(.dt__th) { padding:12px 14px; background:var(--bg-soft,var(--pri-bg)); }
.academic-overview .overview-queue :deep(.dt__td) { padding:12px 14px; font-size:12px; line-height:1.65; }
.academic-overview .overview-queue :deep(.dt__pager) { padding:12px 16px; }
.academic-overview .overview-queue :deep(table) { table-layout:fixed; }
.academic-overview .overview-queue :deep(th:nth-child(1)) { width:25%; }
.academic-overview .overview-queue :deep(th:nth-child(2)) { width:15%; }
.academic-overview .overview-queue :deep(th:nth-child(3)) { width:16%; }
.academic-overview .overview-queue :deep(th:nth-child(4)) { width:13%; }
.academic-overview .overview-queue :deep(th:nth-child(5)) { width:16%; }
.academic-overview .overview-queue :deep(th:nth-child(6)) { width:15%; }
.overview-link { border:0; padding:4px 0; background:transparent; color:var(--pri); font:inherit; font-size:12px; cursor:pointer; }
.overview-title { display:block; white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }
.overview-metrics article { padding:14px; gap:6px; }.overview-metrics strong { font-size:26px; line-height:1.2; }.overview-metrics small { font-size:11px; line-height:1.5; }
.overview-queue > header,.overview-relay h2 { padding:12px 16px; line-height:1.4; }.overview-search { padding:12px 16px; }.overview-search input { max-width:220px; }
</style>
