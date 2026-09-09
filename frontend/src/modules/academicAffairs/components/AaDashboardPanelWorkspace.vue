<template>
  <ModulePageShell class="adp" :title="definition.title" :subtitle="definition.description">
    <template #actions>
      <AppButton variant="ghost" @click="openOverview">返回运行总览</AppButton>
      <AppButton :loading="loading" @click="load">刷新数据</AppButton>
    </template>
    <p class="adp-intro">{{ definition.description }}</p>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="data.scopeRestricted" title="当前范围暂不提供教务汇总" description="请从业务菜单进入本人或本院工作区；运行总览仍可查看授权范围内的学期准备事项。" />
    <template v-else>
      <div class="adp-context"><span>{{ scopeText }}</span><span v-if="data.generatedAt">更新于 {{ sourceTimeLabel(data.generatedAt) }}</span></div>

      <template v-if="panel === 'todos'">
        <nav class="adp-categories" aria-label="待办分类">
          <button :aria-pressed="!category" @click="selectCategory('')">全部分类 <b>{{ totalTodos }}</b></button>
          <button v-for="group in groups" :key="group.key" :aria-pressed="category === group.key" @click="selectCategory(group.key)">{{ group.label }} <b>{{ group.count ?? '—' }}</b></button>
        </nav>
        <div class="adp-section-title"><h2>待处理事项</h2><span>已提供 {{ todoRows.length }} 条明细 · 各类完整记录请进入业务工作区</span></div>
        <EmptyState v-if="!todoRows.length" :title="selectedTotal > 0 ? '当前汇总未提供具体事项' : '当前分类暂无待办'" :description="selectedTotal > 0 ? '请通过下方分类入口查看完整记录。' : '后续产生待处理事项后，可在这里继续办理。'" />
        <div v-else class="adp-tasks">
          <article v-for="todo in todoRows" :key="`${todo.categoryKey}-${todo.entityType}-${todo.businessId}`" class="adp-task">
            <header><div><span class="adp-kicker">{{ todo.categoryLabel }}</span><h2>{{ todo.title }}</h2></div><span class="adp-deadline">{{ todo.deadline ? `截止 ${formatDate(todo.deadline)}` : '未设置截止时间' }}</span></header>
            <p>{{ todo.reason }}</p>
            <dl><div><dt>责任角色</dt><dd>{{ todo.ownerRole || '待明确' }}</dd></div><div><dt>办理后</dt><dd>{{ todo.nextStep || '请在办理页面查看下一步' }}</dd></div><div><dt>最近变化</dt><dd>{{ todo.recentChange || '暂无变化记录' }}</dd></div></dl>
            <footer><span>事项编号 {{ todo.businessId }}</span><AppButton v-if="canOpen(todo.exactRoute)" variant="primary" @click="go(todo.exactRoute)">{{ todo.primaryAction || '去处理' }}</AppButton><span v-else>当前身份无办理权限</span></footer>
          </article>
        </div>
        <div class="adp-links"><AppButton v-for="group in availableGroups" :key="group.key" variant="ghost" @click="go(group.drillRoute)">查看{{ group.label }}全部记录</AppButton></div>
      </template>

      <template v-else-if="panel === 'todayTeaching' || panel === 'todayCourses'">
        <div class="adp-metrics"><article v-for="metric in todayMetrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value ?? '—' }}</strong></article></div>
        <p v-if="today.note" class="adp-note">{{ today.note }}</p>
        <AppSectionCard title="今日课程安排" :subtitle="`共 ${courses.count ?? '—'} 课次，当前展示 ${courseRows.length} 条；完整课表在课表工作区查看`">
          <EmptyState v-if="!courseRows.length" title="今日暂无可展示课程" :description="courses.note || '当前已发布课表中暂无今日课程。'" />
          <DataTable v-else :columns="courseColumns" :rows="courseRows" row-key="itemId" />
          <div class="adp-links"><AppButton v-if="canOpen(courses.drillRoute)" variant="primary" @click="go(courses.drillRoute)">查看完整课表</AppButton><AppButton @click="switchPanel('scheduleChangeReminders')">调停课提醒</AppButton><AppButton @click="switchPanel('resourceOccupancy')">教学资源占用</AppButton></div>
        </AppSectionCard>
      </template>

      <template v-else-if="panel === 'academicProgress'">
        <section class="adp-process" aria-label="学业过程关注事项">
          <button v-for="step in progressSteps" :key="step.panel" @click="switchPanel(step.panel)"><span>{{ step.label }}</span><strong>{{ step.value ?? '—' }}<small>{{ step.unit }}</small></strong><p>{{ step.description }}</p><span class="adp-process-link">查看明细 →</span></button>
        </section>
        <AppSectionCard title="需要跟进的学业事项" subtitle="展示服务端提供的待办摘要；进入事项后按原流程办理。">
          <EmptyState v-if="!todoRows.length" title="暂无可展示的学业待办明细" description="可从上方成绩、异动、预警和毕业入口查看各业务的当前情况。" />
          <div v-else class="adp-rows"><article v-for="row in todoRows" :key="`${row.categoryKey}-${row.businessId}`"><div><span class="adp-kicker">{{ row.categoryLabel }}</span><h3>{{ row.title }}</h3><p>{{ row.reason }}</p></div><AppButton v-if="canOpen(row.exactRoute)" @click="go(row.exactRoute)">{{ row.primaryAction || '去处理' }}</AppButton></article></div>
        </AppSectionCard>
      </template>

      <template v-else-if="panel === 'dataTrends'">
        <AppSectionCard title="近14天业务发生量" subtitle="学籍异动、调停课、成绩提交与学业预警">
          <EmptyState v-if="!trendHasData" title="近期暂无相关业务发生" :description="source.note || '有业务发生后，将按实际日期呈现趋势。'" />
          <AppG2Chart v-else :spec="trendSpec" :height="320" />
        </AppSectionCard>
      </template>

      <template v-else>
        <div class="adp-metrics"><article><span>{{ summaryLabel }}</span><strong>{{ summaryValue }}</strong></article><article v-if="panel === 'gradeProgress'"><span>提交率</span><strong>{{ source.totalTasks ? `${source.submittedRate ?? '—'}%` : '—' }}</strong></article><article v-if="panel === 'resourceOccupancy'"><span>教室占用率</span><strong>{{ source.totalRooms ? `${source.occupancyRate ?? '—'}%` : '—' }}</strong></article></div>
        <p v-if="source.note" class="adp-note">{{ source.note }}</p>
        <AppSectionCard :title="definition.title" :subtitle="`当前展示 ${detailRows.length} 条摘要；完整记录请进入业务工作区`">
          <EmptyState v-if="!detailRows.length" title="暂无可展示记录" :description="source.note || '当前授权范围内没有相关事项摘要。'" />
          <DataTable v-else :columns="detailColumns" :rows="detailRows" row-key="id"><template #cell-action="{ row }"><AppButton v-if="canOpen(row.target)" size="small" @click="go(row.target)">查看详情</AppButton><span v-else>—</span></template></DataTable>
          <div class="adp-links"><AppButton v-if="canOpen(source.drillRoute)" variant="primary" @click="go(source.drillRoute)">进入{{ definition.title === '成绩提交进度' ? '成绩工作区' : '业务工作区' }}</AppButton></div>
        </AppSectionCard>
      </template>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppG2Chart } from '@/components/common'
import { academicAffairsApi } from '../api/academic-affairs.api'
import { DASHBOARD_PANELS, dashboardTodoRows } from '../config/dashboardPanels'
import { academicStatusLabel } from '../constants/academic-display.constants'
import { canEnterRoute } from '@/security/permissionGate'
import { sourceTimeLabel } from './leadershipWall/aa-wall-presentation.mjs'

const TODO_LABELS = { gradeReview: '成绩审核', gradeLagging: '成绩催交', statusChangeReview: '学籍异动', warningHandle: '预警处置', graduationReview: '毕业复核' }

export default {
  name: 'AaDashboardPanelWorkspace',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, DataTable, AppButton, AppSectionCard, AppG2Chart },
  props: { panel: { type: String, required: true }, ctx: { type: Object, required: true } },
  data() { return { loading: true, error: '', data: {}, requestId: 0,
    courseColumns: [{ key: 'time', title: '节次 / 时间' }, { key: 'courseName', title: '课程' }, { key: 'className', title: '班级' }, { key: 'teacherName', title: '任课教师' }, { key: 'classroom', title: '教室' }, { key: 'state', title: '课表状态' }],
    detailColumns: [{ key: 'title', title: '业务对象' }, { key: 'context', title: '相关信息' }, { key: 'state', title: '当前情况' }, { key: 'time', title: '时间 / 时段' }, { key: 'action', title: '操作' }]
  } },
  computed: {
    definition() { return DASHBOARD_PANELS[this.panel] },
    category() { return typeof this.$route.query.category === 'string' ? this.$route.query.category : '' },
    groups() { return (Array.isArray(this.data.todos) ? this.data.todos : []).map(group => ({ ...group, label: TODO_LABELS[group.key] || group.label })) },
    availableGroups() { return this.groups.filter(group => (!this.category || group.key === this.category) && this.canOpen(group.drillRoute)) },
    totalTodos() { return this.groups.reduce((sum, row) => sum + (Number(row.count) || 0), 0) },
    selectedTotal() { return this.category ? this.groups.find(row => row.key === this.category)?.count ?? 0 : this.totalTodos },
    todoRows() { return dashboardTodoRows(this.groups, this.panel === 'todos' ? this.category : '') },
    today() { return this.data.todayTeaching || {} },
    courses() { return this.data.todayCourses || {} },
    scopeText() { return [this.data.scopeNote || '当前授权范围', ...(this.panel.startsWith('today') ? [this.today.dateLabel, this.today.termLabel] : ['各业务按自身统计范围汇总'])].filter(Boolean).join(' · ') },
    todayMetrics() { return [{ label: '今日课次', value: this.today.totalToday }, { label: '按课表进行中', value: this.today.inProgress }, { label: '调课关联课位', value: this.today.adjustedCount }, { label: '今日考试', value: this.today.examCount }] },
    courseRows() { return (this.courses.items || []).map(row => ({ ...row, time: `第 ${row.slotNo} 节 · ${row.startTime || '—'}–${row.endTime || '—'}`, state: `${row.runStatusLabel || '待确认'}${row.changed ? ' · 已调课' : ''}` })) },
    progressSteps() { return [
      { panel: 'gradeProgress', label: '成绩提交', value: this.data.gradeProgress?.totalTasks, unit: '个任务', description: '核对录入、提交与审核进度' },
      { panel: 'statusChangeReminders', label: '学籍变动', value: this.data.statusChangeReminders?.count, unit: '项待审批', description: '跟进在途异动和审批节点' },
      { panel: 'warningReminders', label: '学业预警', value: this.data.warningReminders?.count, unit: '项待处置', description: '跟进学生风险与处置责任' },
      { panel: 'graduationWarnings', label: '毕业资格', value: this.data.graduationWarnings?.count, unit: '项待关注', description: '查看异常、待复核和延期事项' }
    ] },
    source() { return this.data[this.panel] || {} },
    summaryLabel() { return this.panel === 'gradeProgress' ? '成绩任务总数' : this.panel === 'resourceOccupancy' ? '今日占用教室' : '当前关注事项' },
    summaryValue() { return (this.panel === 'gradeProgress' ? this.source.totalTasks : this.panel === 'resourceOccupancy' ? this.source.occupiedToday : this.source.count) ?? '—' },
    detailRows() {
      const rows = this.panel === 'gradeProgress' ? this.source.pendingTasks || [] : this.source.items || []
      return rows.map((row, index) => ({
        id: row.gradeTaskId || row.changeId || row.warningId || row.resultId || row.examCourseId || row.classroom || String(index),
        title: row.courseName || row.studentName || row.classroom || '业务记录',
        context: [row.className, row.teacherName, row.batchName, row.changeTypeLabel].filter(Boolean).join(' · ') || '—',
        state: row.reason || row.conclusion || row.statusLabel || (row.status ? academicStatusLabel(row.status) : row.useCount != null ? `${row.useCount} 次使用` : row.batchStatus ? academicStatusLabel(row.batchStatus) : '—'),
        time: row.examDate ? `${row.examDate} ${row.startTime || ''}–${row.endTime || ''}` : row.slots ? `节次 ${row.slots.join('、')}` : this.formatDate(row.deadline || row.submittedAt),
        target: row.exactRoute || (row.gradeTaskId ? `/admin/academic-affairs/grade-entry?taskId=${encodeURIComponent(row.gradeTaskId)}` : '')
      }))
    },
    trendRows() { return (this.source.series || []).flatMap(series => (series.points || []).map(point => ({ date: point.date, value: point.value, series: series.label }))) },
    trendHasData() { return this.trendRows.some(row => Number(row.value) > 0) },
    trendSpec() { return { type: 'line', data: this.trendRows, encode: { x: 'date', y: 'value', color: 'series' }, legend: { color: { position: 'bottom' } } } }
  },
  created() { this.load() },
  beforeUnmount() { this.requestId++ },
  watch: { 'ctx.ctxKey'() { this.load() } },
  methods: {
    sourceTimeLabel,
    formatDate(value) { return value ? String(value).replace('T', ' ').replace(/\.\d+$/, '').replace(/ 00:00:00$/, '') : '—' },
    async load() {
      const requestId = ++this.requestId
      this.loading = true; this.error = ''; this.data = {}
      try {
        const response = await academicAffairsApi.getDashboardReminders()
        if (requestId !== this.requestId) return
        if (response.code !== 0) throw new Error(response.message || '教务数据读取失败')
        this.data = response.data || {}
      } catch (error) { if (requestId === this.requestId) this.error = error?.message || '教务数据读取失败' }
      finally { if (requestId === this.requestId) this.loading = false }
    },
    selectCategory(category) { const query = { ...this.$route.query }; if (category) query.category = category; else delete query.category; this.$router.push({ path: this.$route.path, query }) },
    switchPanel(panel) { this.$router.push({ path: '/admin/academic-affairs', query: { panel } }) },
    openOverview() { this.$router.push('/admin/academic-affairs') },
    canOpen(target) {
      if (!target) return false
      try {
        const route = this.$router.resolve(String(target).startsWith('/') ? target : { name: target })
        if (!route.matched?.length) return false
        return canEnterRoute(route.meta)
      } catch { return false }
    },
    go(target) { if (this.canOpen(target)) this.$router.push(String(target).startsWith('/') ? target : { name: target }) }
  }
}
</script>

<style scoped>
.adp-intro { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
.adp-context { display: flex; justify-content: space-between; gap: 8px 12px; flex-wrap: wrap; color: var(--text-secondary); font-size: 12px; margin-bottom: 4px; }
.adp-categories { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.adp-categories button { border: 1px solid var(--border-base, #dbe4f3); background: var(--bg-card, white); padding: 7px 10px; min-height: 34px; border-radius: 8px; color: var(--text-primary); font: inherit; cursor: pointer; }
.adp-categories button[aria-pressed=true] { color: var(--pri, #285bb5); background: var(--pri-bg, #edf3ff); border-color: var(--pri, #285bb5); }
.adp-categories b { margin-left: 8px; font-variant-numeric: tabular-nums; }
.adp-section-title { display: flex; justify-content: space-between; gap: 8px 12px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.adp-section-title h2 { font-size: 17px; margin: 0; }.adp-section-title span { font-size: 12px; color: var(--text-secondary); }
.adp-tasks { display: grid; gap: 10px; }.adp-task { border: 1px solid var(--border-base, #dbe4f3); border-radius: 12px; background: var(--bg-card, white); padding: 14px; }
.adp-task header, .adp-task footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.adp-task h2, .adp-rows h3 { margin: 5px 0; font-size: 16px; line-height: 1.6; }.adp-kicker { color: var(--pri, #285bb5); font-size: 12px; }.adp-deadline { font-size: 12px; color: var(--text-secondary); }
.adp-task p, .adp-rows p { color: var(--text-secondary); line-height: 1.7; }.adp-task dl { display: grid; gap: 8px; }.adp-task dl div { display: grid; grid-template-columns: 72px minmax(0,1fr); font-size: 13px; }.adp-task dt, .adp-task footer span { color: var(--text-secondary); }.adp-task dd { margin: 0; overflow-wrap: anywhere; }
.adp-links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.adp-metrics, .adp-process { display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 10px; margin-bottom: 8px; }
.adp-metrics article, .adp-process button { padding: 14px; border: 1px solid var(--border-base, #dbe4f3); border-radius: 10px; background: var(--bg-card,white); min-width: 0; }
.adp-metrics strong, .adp-process strong { display: block; font-size: 24px; font-variant-numeric: tabular-nums; margin-top: 6px; }.adp-metrics span { color: var(--text-secondary); }
.adp-process button { text-align: left; font: inherit; color: var(--text-primary); cursor: pointer; }.adp-process small { font-size: 12px; font-weight: 400; margin-left: 6px; }.adp-process p { margin: 7px 0; font-size: 12px; line-height: 1.5; color: var(--text-secondary); }.adp-process-link { color: var(--pri, #285bb5); font-size: 12px; }
.adp-process button:hover { border-color: var(--pri, #285bb5); }.adp button:focus-visible { outline: 2px solid var(--pri, #285bb5); outline-offset: 3px; }
.adp-note { padding: 9px 12px; background: var(--pri-bg, #edf3ff); border-radius: 8px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 8px; }
.adp-rows article { display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--border-base, #dbe4f3); padding: 16px 0; }
@container academic-body (max-width: 550px) { .adp-metrics, .adp-process { grid-template-columns: repeat(2,minmax(0,1fr)); }.adp-process button, .adp-metrics article { padding: 14px; }.adp-rows article { align-items: flex-start; flex-direction: column; } }
@container academic-body (max-width: 350px) { .adp-metrics, .adp-process { grid-template-columns: minmax(0,1fr); } }
</style>
