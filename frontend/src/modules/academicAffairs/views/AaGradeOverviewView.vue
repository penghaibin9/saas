<template>
  <ModulePageShell
    title="成绩总览"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="secondary" @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</AppButton>
      <AppButton v-if="canInput || canManageScheme" variant="primary" @click="$router.push('/admin/academic-affairs/grade-entry')">{{ canInput ? '成绩录入' : '课程成绩构成' }}</AppButton>
    </template>

    <div class="mp-stack">
      <form class="aa-filter aa-queue-filter" aria-label="成绩任务查询" @submit.prevent="searchTasks">
        <label class="aa-filter-field"><span>学期</span><AppTermCodePicker v-model="taskTerm" placeholder="全部学期" /></label>
        <label class="aa-filter-field"><span>任务状态</span><AppSelect v-model="taskStatus" :options="taskStatusOptions" placeholder="全部任务" /></label>
        <label class="aa-filter-field"><span>课程名称</span><AppTextInput v-model="taskKeyword" placeholder="输入课程名称" /></label>
        <AppButton variant="primary" @click="searchTasks">查询任务</AppButton>
        <AppButton variant="ghost" @click="clearTaskFilters">清空</AppButton>
      </form>
      <AppSectionCard title="成绩任务">
        <template #header>
          <span v-if="!tasksLoading && !taskError" class="aa-task-count">共 <strong>{{ taskTotal }}</strong> 门</span>
        </template>
        <template #header-extra><AppButton variant="ghost" @click="loadTasks">刷新</AppButton></template>
        <ErrorState v-if="taskError" :description="taskError" @retry="loadTasks" />
        <LoadingState v-else-if="tasksLoading" />
        <EmptyState v-else-if="!tasks.length" title="当前查询条件下没有成绩任务" description="可清空筛选后再查" />
        <DataTable v-else :columns="taskColumns" :rows="tasks" row-key="gradeTaskId">
          <template #cell-courseName="{ row }">
            <div class="mp-cell-main">{{ row.courseName }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassName || '教学班待核对' }}</div>
          </template>
          <template #cell-teacher="{ row }">{{ row.teacherAuthorityReady && row.teacherNames?.length ? row.teacherNames.map(teacherText).join('、') : '任课教师待核对' }}</template>
          <template #cell-status="{ row }"><AppStatusTag :type="gradeStatusType(row.status)" dot>{{ gradeStatusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-responsibility="{ row }"><AcademicObjectResponsibility compact :object-id="row.gradeTaskId" :responsibility="row.responsibility" :next-step="row.nextStep" /></template>
          <template #cell-deadline="{ row }">{{ row.deadline || '尚未设置' }}</template>
          <template #cell-actions="{ row }"><button class="mp-link" @click="openTask(row)">{{ gradeTaskDestination(row).label }}</button></template>
        </DataTable>
        <div v-if="taskTotal > 20" class="aa-task-pages"><AppButton variant="ghost" :disabled="taskPage <= 1" @click="changeTaskPage(taskPage - 1)">上一页</AppButton><span>第 {{ taskPage }} / {{ Math.max(1, Math.ceil(taskTotal / 20)) }} 页</span><AppButton variant="ghost" :disabled="taskPage * 20 >= taskTotal" @click="changeTaskPage(taskPage + 1)">下一页</AppButton></div>
      </AppSectionCard>
      <AppButton variant="ghost" @click="toggleAnalysis">{{ showAnalysis ? '收起成绩分析' : '查看已发布成绩分析' }}</AppButton>
      <section v-if="showAnalysis" class="mp-stack" aria-label="已发布成绩分析">
      <div class="aa-filter">
        <span class="aa-filter__label">学期</span>
        <AppTermCodePicker v-model="term" placeholder="全部学期" style="max-width:220px" />
        <span class="aa-filter__label">分组维度</span>
        <AppSelect v-model="dimension" :options="dimensionOptions" style="min-width:130px" @change="load" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="aa-metric-grid">
          <AppMetricCard title="总成绩记录" :value="data.total" unit="条" />
          <AppMetricCard title="及格率" :value="pct(data.passRate)" unit="%" />
          <AppMetricCard title="优秀率" :value="pct(data.excellentRate)" unit="%" />
          <AppMetricCard title="平均分" :value="data.avgScore ?? '待核对'" />
          <AppMetricCard title="最高分" :value="data.maxScore ?? '待核对'" />
          <AppMetricCard title="最低分" :value="data.minScore ?? '待核对'" />
        </div>

        <AppSectionCard title="分数段分布">
          <EmptyState v-if="!data.total" title="暂无成绩数据" description="发布成绩录入任务后，这里出现分数段分布" />
          <template v-else>
            <AppG2Chart :spec="distSpec" :height="260" />
            <div class="aa-dist">
              <div v-for="d in data.distribution" :key="d.range" class="aa-dist__row">
                <span class="aa-dist__label">{{ d.range }}</span>
                <div class="aa-dist__bar-wrap"><div class="aa-dist__bar" :style="{ width: barWidth(d.count) }"></div></div>
                <span class="aa-dist__count">{{ d.count }}</span>
              </div>
            </div>
          </template>
        </AppSectionCard>

        <AppSectionCard v-if="dimension" :title="dimension === 'course' ? '按课程成绩分析统计表' : '按班级成绩分析统计表'">
          <div class="aa-export">
            <AppTextInput v-model="exportPurpose" placeholder="导出用途（≥5 字，写审计）" size="compact" style="max-width:280px" />
            <AppButton variant="primary" :loading="downloading" @click="doExport">导出 Excel</AppButton>
          </div>
          <EmptyState v-if="!(data.rows && data.rows.length)" title="暂无分组数据" description="该学期下暂无已发布成绩" />
          <DataTable v-else :columns="columns" :rows="data.rows" row-key="name">
            <template #cell-passRate="{ row }">{{ pct(row.passRate) }}%</template>
            <template #cell-excellentRate="{ row }">{{ pct(row.excellentRate) }}%</template>
          </DataTable>
        </AppSectionCard>
      </template>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import AcademicObjectResponsibility from '../components/AcademicObjectResponsibility.vue'

/** 成绩分析（/admin/academic-affairs/grade-overview）：GET /grade-views/analysis（可按课程/班级分组）+ 导出 xlsx。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppSelect, AppTextInput, AppG2Chart, AppTermCodePicker, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError, gradeStatusLabel, gradeQueueState, gradeTaskDestination } from './parallel-c/grade-review'

export default {
  name: 'AaGradeOverviewView',
  components: {
    AcademicObjectResponsibility, ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
      AppButton, AppMetricCard, AppSectionCard, AppSelect, AppTextInput, AppG2Chart, AppTermCodePicker, AppStatusTag
  },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      alive: true, readSeq: 0, taskSeq: 0, exportSeq: 0, showAnalysis: false, tasks: [], tasksLoading: false, taskError: '', taskPage: 1, taskTotal: 0, taskStatus: '', taskTerm: '', taskKeyword: '',
      taskStatusOptions: [{ value: '', label: '全部任务' }, ...['NOT_STARTED', 'INPUTTING', 'RETURNED', 'SUBMITTED', 'ACADEMIC_REVIEW', 'PUBLISHED', 'ARCHIVED'].map(value => ({ value, label: gradeStatusLabel(value) }))],
      taskColumns: [{ key: 'courseName', title: '课程 / 教学班' }, { key: 'termCode', title: '学期' }, { key: 'teacher', title: '任课教师' }, { key: 'status', title: '状态' }, { key: 'responsibility', title: '当前负责' }, { key: 'deadline', title: '提交截止' }, { key: 'actions', title: '操作' }],
      loading: false, error: '', term: '', dimension: '',
      data: { total: null, passRate: null, excellentRate: null, avgScore: null, maxScore: null, minScore: null, distribution: [], rows: [] },
      exportPurpose: '', downloading: false,
      dimensionOptions: [
        { label: '总体', value: '' }, { label: '按课程', value: 'course' }, { label: '按班级', value: 'class' }
      ]
    }
  },
  computed: {
    canInput() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.grade.input') },
    canManageScheme() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.grade.scheme.manage') },
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope]) },
    maxCount() { return Math.max(1, ...(this.data.distribution || []).map((d) => d.count)) },
    distSpec() {
      return {
        type: 'interval',
        data: (this.data.distribution || []).map((d) => ({ name: d.range, value: d.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    columns() {
      return [
        { key: 'name', title: this.dimension === 'course' ? '课程' : '班级' },
        { key: 'total', title: '记录数', align: 'center' }, { key: 'avgScore', title: '平均分', align: 'center' },
        { key: 'maxScore', title: '最高', align: 'center' }, { key: 'minScore', title: '最低', align: 'center' },
        { key: 'passRate', title: '及格率', align: 'center' }, { key: 'excellentRate', title: '优秀率', align: 'center' }
      ]
    }
  },
  created() { this.restoreTaskQuery() },
  watch: { '$route.fullPath'() { this.restoreTaskQuery() }, identityKey() { this.invalidate(); this.restoreTaskQuery() }, term: { flush: 'sync', handler() { this.clearAnalysis() } }, dimension: { flush: 'sync', handler() { this.clearAnalysis() } } },
  beforeUnmount() { this.alive = false; this.invalidate() },
  methods: {
    gradeStatusLabel,
    gradeTaskDestination,
    gradeStatusType(status) { return ({ PUBLISHED: 'success', ARCHIVED: 'info', RETURNED: 'danger', SUBMITTED: 'warning', COLLEGE_REVIEW: 'warning', ACADEMIC_REVIEW: 'warning', INPUTTING: 'primary' })[status] || 'default' },
    teacherText(name) { return String(name || '').replace(/\s*[（(][A-Za-z0-9_.@-]+[)）]\s*$/, '') },
    taskStage(status) { return ({ NOT_STARTED: 1, INPUTTING: 2, RETURNED: 2, SUBMITTED: 3, COLLEGE_REVIEW: 3, ACADEMIC_REVIEW: 4, PUBLISHED: 5, ARCHIVED: 5 })[status] || 0 },
    clearAnalysis() { this.readSeq++; this.exportSeq++; this.loading = false; this.downloading = false; this.error = ''; this.data = { distribution: [], rows: [] } },
    invalidate() { this.readSeq++; this.taskSeq++; this.exportSeq++; this.tasks = []; this.taskTotal = 0; this.taskPage = 1; this.data = { distribution: [], rows: [] }; this.showAnalysis = false; this.exportPurpose = ''; this.downloading = false; this.loading = false; this.tasksLoading = false; this.error = ''; this.taskError = '' },
    toggleAnalysis() { this.showAnalysis = !this.showAnalysis; if (this.showAnalysis) this.load() },
    restoreTaskQuery() {
      const state = gradeQueueState(this.$route?.query)
      this.taskStatus = state.status; this.taskTerm = state.term; this.taskKeyword = state.keyword; this.taskPage = state.page
      return this.loadTasks()
    },
    async navigateTaskQuery(page) {
      const before = this.$route.fullPath
      await this.$router.push({ path: this.$route.path, query: { ...this.$route.query, status: this.taskStatus || undefined, term: this.taskTerm || undefined, keyword: this.taskKeyword.trim() || undefined, page: String(page) } })
      // A query on the same URL still refreshes the authoritative queue.
      if (before === this.$route.fullPath) return this.restoreTaskQuery()
    },
    searchTasks() { return this.navigateTaskQuery(1) },
    clearTaskFilters() { this.taskStatus = ''; this.taskTerm = ''; this.taskKeyword = ''; return this.searchTasks() },
    changeTaskPage(page) { return this.navigateTaskQuery(page) },
    openTask(row) {
      const destination = gradeTaskDestination(row), returnToken = this.academicFlow?.captureReturn?.()
      this.$router.push({ path: `/admin/academic-affairs/${destination.page}`, query: { taskId: String(row.gradeTaskId), ...(destination.tab ? { tab: destination.tab } : {}), ...(returnToken ? { returnToken } : {}) } })
    },
    async loadTasks() {
      const seq = ++this.taskSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.taskSeq && identity === this.identityKey
      this.tasksLoading = true; this.taskError = ''; this.tasks = []; this.taskTotal = 0
      const state = gradeQueueState(this.$route?.query)
      if (state.error) { this.taskError = state.error; this.tasksLoading = false; return }
      try {
        const res = await academicAffairsApi.getGradeTasks({ status: state.status || undefined, term: state.term || undefined, keyword: state.keyword || undefined, page: state.page, pageSize: 20 })
        if (!valid()) return
        if (res.code !== 0) throw res
        this.tasks = res.data?.list || []; this.taskTotal = res.data?.total ?? this.tasks.length
      } catch (err) { if (valid()) this.taskError = gradeError(err, '成绩任务读取失败，请重试。') }
      finally { if (valid()) this.tasksLoading = false }
    },
    pct(v) { return v == null ? '待核对' : Math.round(v * 100) },
    barWidth(count) { return Math.round((count / this.maxCount) * 100) + '%' },
    async load() {
      const seq = ++this.readSeq, identity = this.identityKey, term = this.term, dimension = this.dimension
      const valid = () => this.alive && seq === this.readSeq && identity === this.identityKey && term === this.term && dimension === this.dimension
      this.loading = true; this.error = ''; this.data = { distribution: [], rows: [] }
      try {
        const res = await academicAffairsApi.getGradeAnalysis(term || undefined, dimension || undefined)
        if (!valid()) return
        if (res.code !== 0) throw res
        this.data = { distribution: [], rows: [], ...res.data }
      } catch (err) { if (valid()) this.error = gradeError(err, '成绩分析读取失败，请重试。') }
      finally { if (valid()) this.loading = false }
    },
    async doExport() {
      if (this.downloading || this.loading) return
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      const seq = ++this.exportSeq, identity = this.identityKey, term = this.term, dimension = this.dimension
      const valid = () => this.alive && seq === this.exportSeq && identity === this.identityKey && term === this.term && dimension === this.dimension
      this.downloading = true
      try {
      const res = await academicAffairsApi.exportGradeAnalysis({
        term: this.term || undefined,
        dimension: this.dimension || 'course',
        purpose: this.exportPurpose.trim()
      })
      if (!valid()) return
      if (res.code !== 0) {
        toast.error(gradeError(res, '导出失败，请核对后重试。'))
        return
      }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `成绩分析统计表-${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      toast.success('导出成功')
      } catch (err) { if (valid()) toast.error(gradeError(err, '导出失败，请核对后重试。')) }
      finally { if (valid()) this.downloading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-overview-summary { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 12px; }
.aa-overview-summary article { padding: 10px 14px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-queue-filter { align-items: end; }
.aa-filter-field { display: grid; gap: 6px; min-width: 150px; flex: 1; }
.aa-overview-summary small, .aa-overview-summary strong, .aa-overview-summary span { display: block; }
.aa-overview-summary small, .aa-overview-summary span { color: var(--text-secondary); font-size: 12px; }
.aa-overview-summary strong { margin: 10px 0; font-size: 26px; color: var(--text-primary); }
.aa-task-progress-list { display: grid; gap: 22px; padding: 12px 0; }
.aa-task-progress-row { display: grid; grid-template-columns: minmax(180px,1fr) minmax(180px,2fr) auto; gap: 16px; align-items: center; }
.aa-task-progress-row strong { display: block; font-size: 13px; }
.aa-task-progress-row small { display: block; margin-top: 6px; color: var(--text-secondary); font-size: 11px; }
.aa-task-stage__track { display: grid; grid-template-columns: repeat(5,1fr); gap: 3px; }
.aa-task-stage__track i { height: 9px; border-radius: 4px; background: var(--pri-bg); }
.aa-task-stage__track i.complete { background: var(--pri); }
@media(max-width: 800px) { .aa-overview-summary { grid-template-columns: repeat(2,minmax(0,1fr)); }.aa-task-progress-row { grid-template-columns: minmax(0,1fr) auto; }.aa-task-stage { grid-column: 1 / -1; grid-row: 2; } }
.aa-task-count { margin-left: 10px; color: var(--text-secondary); font-size: 13px; }
.aa-task-count strong { color: var(--pri); font-size: 16px; }
.aa-task-pages { display: flex; justify-content: center; gap: 14px; align-items: center; margin-top: 16px; }
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-dist__row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-dist__label { width: 72px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-dist__bar-wrap { flex: 1; height: 18px; background: var(--fill-100, #f2f3f5); border-radius: 4px; overflow: hidden; }
.aa-dist__bar { height: 100%; background: var(--primary-400, #60a5fa); border-radius: 4px; }
.aa-dist__count { width: 48px; text-align: right; font-size: 13px; color: var(--text-900, #1f2329); }
.aa-export { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
</style>
