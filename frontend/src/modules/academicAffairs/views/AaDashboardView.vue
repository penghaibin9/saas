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

      <!-- 成绩提交进度 -->
      <AppSectionCard id="adb-grade-progress" title="成绩提交进度" subtitle="成绩录入任务状态分布 + 滞后任务前 10 条">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-grade-overview' })">成绩总览 →</button>
        </template>
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <div class="aa-metric-grid">
            <AppMetricCard title="成绩任务总数" :value="gradeProgress.totalTasks || 0" unit="个" />
            <AppMetricCard title="已提交/审核/发布" :value="gradeSubmittedCount" unit="个" />
            <AppMetricCard title="提交率" :value="gradeProgress.submittedRate || 0" unit="%" />
          </div>
          <EmptyState
            v-if="!gradeProgress.pendingTasks || !gradeProgress.pendingTasks.length"
            title="暂无滞后任务"
            description="所有成绩录入任务均已提交或不存在滞后任务"
          />
          <DataTable v-else :columns="gradeColumns" :rows="gradeProgress.pendingTasks" row-key="gradeTaskId">
            <template #cell-status="{ row }">
              <AppStatusTag :status="row.status" :label="row.statusLabel" />
            </template>
            <template #cell-progressRate="{ row }">{{ row.enteredCount }}/{{ row.rosterCount }}（{{ row.progressRate }}%）</template>
          </DataTable>
        </div>
      </AppSectionCard>

      <!-- 考试安排提醒 -->
      <AppSectionCard
        id="adb-exam-reminders"
        title="考试安排提醒"
        :subtitle="'未来 ' + (examReminders.windowDays || 14) + ' 天内已确认排考的考试'"
      >
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-exam' })">考务管理 →</button>
        </template>
        <div v-if="!remindersLoading && !remindersError" class="mp-stack">
          <EmptyState
            v-if="!examReminders.items || !examReminders.items.length"
            title="暂无临近考试"
            description="近期无已确认排考的考试安排"
          />
          <DataTable v-else :columns="examColumns" :rows="examReminders.items" row-key="examCourseId" />
        </div>
      </AppSectionCard>

      <!-- 学籍异动提醒 -->
      <AppSectionCard id="adb-status-change-reminders" title="学籍异动提醒" subtitle="在途待审批的学籍异动申请">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-status-changes' })">学籍异动 →</button>
        </template>
        <div v-if="!remindersLoading && !remindersError" class="mp-stack">
          <EmptyState
            v-if="!statusChangeReminders.items || !statusChangeReminders.items.length"
            title="暂无在途异动"
            description="当前没有待审批的学籍异动申请"
          />
          <DataTable v-else :columns="statusChangeColumns" :rows="statusChangeReminders.items" row-key="changeId">
            <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
          </DataTable>
        </div>
      </AppSectionCard>

      <!-- 学业预警提醒 -->
      <AppSectionCard id="adb-warning-reminders" title="学业预警提醒" subtitle="在办（待处置）学业预警，高等级优先">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-warnings' })">学业预警 →</button>
        </template>
        <div v-if="!remindersLoading && !remindersError" class="mp-stack">
          <EmptyState
            v-if="!warningReminders.items || !warningReminders.items.length"
            title="暂无在办预警"
            description="当前没有待处置的学业预警"
          />
          <DataTable v-else :columns="warningColumns" :rows="warningReminders.items" row-key="warningId">
            <template #cell-level="{ row }"><AppRiskTag :level="row.level" /></template>
          </DataTable>
        </div>
      </AppSectionCard>

      <!-- 毕业资格预警 -->
      <AppSectionCard id="adb-graduation-warnings" title="毕业资格预警" subtitle="预审异常 / 待学院复核 / 待教务终审 / 延毕">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-graduation' })">毕业资格预审 →</button>
        </template>
        <div v-if="!remindersLoading && !remindersError" class="mp-stack">
          <EmptyState
            v-if="!graduationWarnings.items || !graduationWarnings.items.length"
            title="暂无预警"
            description="当前没有异常或待复核的毕业资格预审结果"
          />
          <DataTable v-else :columns="graduationColumns" :rows="graduationWarnings.items" row-key="resultId">
            <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
          </DataTable>
        </div>
      </AppSectionCard>

      <!-- 教务待办 -->
      <AppSectionCard id="adb-todos" title="教务待办" subtitle="跨模块待处理事项聚合，点击直达处理页面">
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <EmptyState v-if="!todos.length" title="暂无待办" description="当前数据范围内没有待处理事项" />
          <div v-for="t in todos" :key="t.key" class="mp-kv aa-todo-row">
            <span class="mp-kv__k">
              <AppStatusTag :type="t.count > 0 ? 'warning' : 'default'" dot>{{ t.count }}</AppStatusTag>
              <span>{{ t.label }}</span>
            </span>
            <button class="mp-link" :disabled="!t.count" @click="$router.push({ name: t.drillRoute })">去处理</button>
          </div>
        </div>
      </AppSectionCard>

      <!-- 今日教学运行 -->
      <AppSectionCard id="adb-today-teaching" title="今日教学运行" :subtitle="todayTeachingSubtitle">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-schedule' })">课表管理 →</button>
        </template>
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <div class="aa-metric-grid">
            <AppMetricCard title="今日课次" :value="todayTeaching.totalToday || 0" unit="节" />
            <AppMetricCard title="进行中" :value="todayTeaching.inProgress || 0" unit="节" />
            <AppMetricCard title="未开始" :value="todayTeaching.notStarted || 0" unit="节" />
            <AppMetricCard title="已结束" :value="todayTeaching.ended || 0" unit="节" />
            <AppMetricCard title="今日调课" :value="todayTeaching.adjustedCount || 0" unit="节" />
            <AppMetricCard title="今日考试" :value="todayTeaching.examCount || 0" unit="场" />
            <AppMetricCard title="涉及教师" :value="todayTeaching.teacherCount || 0" unit="人" />
            <AppMetricCard title="涉及班级" :value="todayTeaching.classCount || 0" unit="个" />
            <AppMetricCard title="涉及教室" :value="todayTeaching.roomCount || 0" unit="间" />
          </div>
          <EmptyState v-if="todayTeaching.note" :title="todayTeaching.note" description="" />
        </div>
      </AppSectionCard>

      <!-- 今日课程 -->
      <AppSectionCard id="adb-today-courses" title="今日课程" :subtitle="'共 ' + (todayCourses.count || 0) + ' 节，按节次排序'">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-schedule' })">课表管理 →</button>
        </template>
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <EmptyState
            v-if="!todayCourses.items || !todayCourses.items.length"
            title="今日暂无课程"
            :description="todayCourses.note || '当前无排课数据'"
          />
          <template v-else>
            <DataTable :columns="todayCourseColumns" :rows="todayCourses.items" row-key="itemId">
              <template #cell-courseName="{ row }">
                {{ row.courseName }}
                <AppStatusTag v-if="row.changed" type="warning" size="sm">调停课</AppStatusTag>
              </template>
              <template #cell-time="{ row }">{{ row.startTime || '-' }} ~ {{ row.endTime || '-' }}</template>
              <template #cell-runStatus="{ row }">
                <AppStatusTag :type="runStatusTagType(row.runStatus)" :label="row.runStatusLabel" />
              </template>
            </DataTable>
            <div v-if="todayCourses.count > todayCourses.shown" class="aa-more-hint">
              仅显示前 {{ todayCourses.shown }} 条，共 {{ todayCourses.count }} 条，完整列表见「课表管理」
            </div>
          </template>
        </div>
      </AppSectionCard>

      <!-- 调停课提醒 -->
      <AppSectionCard id="adb-schedule-change-reminders" title="调停课提醒" subtitle="在途待审批的调课/停课/补课申请">
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-schedule-change-ledger' })">调停课台账 →</button>
        </template>
        <div v-if="!remindersLoading && !remindersError" class="mp-stack">
          <EmptyState
            v-if="!scheduleChangeReminders.items || !scheduleChangeReminders.items.length"
            title="暂无在途调停课申请"
            description="当前没有待审批的调课/停课/补课申请"
          />
          <DataTable v-else :columns="scheduleChangeColumns" :rows="scheduleChangeReminders.items" row-key="changeId">
            <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
          </DataTable>
        </div>
      </AppSectionCard>

      <!-- 教学资源占用 -->
      <AppSectionCard
        id="adb-resource-occupancy"
        title="教学资源占用"
        :subtitle="'今日教室占用率 ' + (resourceOccupancy.occupancyRate || 0) + '%（' + (resourceOccupancy.occupiedToday || 0) + '/' + (resourceOccupancy.totalRooms || 0) + '）'"
      >
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-classrooms' })">教室资源 →</button>
        </template>
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <div class="aa-metric-grid">
            <AppMetricCard title="可用教室" :value="resourceOccupancy.totalRooms || 0" unit="间" />
            <AppMetricCard title="今日已占用" :value="resourceOccupancy.occupiedToday || 0" unit="间" />
            <AppMetricCard title="占用率" :value="resourceOccupancy.occupancyRate || 0" unit="%" />
          </div>
          <EmptyState
            v-if="!resourceOccupancy.items || !resourceOccupancy.items.length"
            :title="resourceOccupancy.note || '今日暂无教室占用记录'"
            description=""
          />
          <template v-else>
            <DataTable :columns="resourceColumns" :rows="resourceOccupancy.items" row-key="classroom">
              <template #cell-slots="{ row }">{{ formatSlots(row.slots) }}</template>
            </DataTable>
            <div v-if="resourceOccupancy.note" class="aa-more-hint">{{ resourceOccupancy.note }}</div>
          </template>
        </div>
      </AppSectionCard>

      <!-- 教务数据趋势 -->
      <AppSectionCard
        id="adb-data-trends"
        title="教务数据趋势"
        :subtitle="'近 ' + (dataTrends.days ? dataTrends.days.length : 14) + ' 天学籍异动申请/调停课申请/成绩提交/新增学业预警的真实业务发生量'"
      >
        <template #header-extra>
          <button class="mp-link" @click="$router.push({ name: 'aa-stats' })">教务统计 →</button>
        </template>
        <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
        <LoadingState v-else-if="remindersLoading" />
        <div v-else class="mp-stack">
          <EmptyState v-if="!trendHasData" title="近期暂无相关业务发生" :description="dataTrends.note || ''" />
          <AppG2Chart v-else :spec="trendChartSpec" :height="260" />
        </div>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教务看板（/admin/academic-affairs）：GET /academic-affairs/dashboard + GET /academic-affairs/dashboard/reminders。
 * 当前学期 + 指标卡 + 模块状态 + 六卡提醒（成绩提交进度/考试安排/学籍异动/学业预警/毕业资格预警/教务待办）+
 * 续工五卡（今日教学运行/今日课程/调停课提醒/教学资源占用/教务数据趋势，2026-07-16 第三轮）。
 * ?panel= 深链接滚动定位到对应分栏（对齐岗位实习看板 InternshipDashboardView 同款 PANEL_ANCHORS 模式）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard, AppStatusTag, AppRiskTag, AppG2Chart } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中' }
const RUN_STATUS_TYPE = { NOT_STARTED: 'default', IN_PROGRESS: 'processing', ENDED: 'info', UNKNOWN: 'default' }

const PANEL_ANCHORS = {
  gradeProgress: 'adb-grade-progress',
  examReminders: 'adb-exam-reminders',
  statusChangeReminders: 'adb-status-change-reminders',
  warningReminders: 'adb-warning-reminders',
  graduationWarnings: 'adb-graduation-warnings',
  todos: 'adb-todos',
  todayTeaching: 'adb-today-teaching',
  todayCourses: 'adb-today-courses',
  scheduleChangeReminders: 'adb-schedule-change-reminders',
  resourceOccupancy: 'adb-resource-occupancy',
  dataTrends: 'adb-data-trends'
}

export default {
  name: 'AaDashboardView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppMetricCard, AppSectionCard, AppStatusTag, AppRiskTag, AppG2Chart
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      currentTerm: null,
      summaryCards: [],
      moduleCards: [],
      // 六卡提醒
      remindersLoading: true,
      remindersError: '',
      gradeProgress: {},
      examReminders: {},
      statusChangeReminders: {},
      warningReminders: {},
      graduationWarnings: {},
      todos: [],
      // 续工五卡
      todayTeaching: {},
      todayCourses: {},
      scheduleChangeReminders: {},
      resourceOccupancy: {},
      dataTrends: {},
      todayCourseColumns: [
        { key: 'slotNo', title: '节次' },
        { key: 'time', title: '时间' },
        { key: 'courseName', title: '课程' },
        { key: 'className', title: '班级' },
        { key: 'teacherName', title: '任课教师' },
        { key: 'classroom', title: '教室' },
        { key: 'runStatus', title: '状态' }
      ],
      scheduleChangeColumns: [
        { key: 'changeTypeLabel', title: '类型' },
        { key: 'courseName', title: '课程' },
        { key: 'className', title: '班级' },
        { key: 'teacherName', title: '教师' },
        { key: 'currentNode', title: '当前节点' },
        { key: 'status', title: '状态' },
        { key: 'submittedAt', title: '提交时间' }
      ],
      resourceColumns: [
        { key: 'classroom', title: '教室' },
        { key: 'useCount', title: '占用次数' },
        { key: 'slots', title: '节次' }
      ],
      gradeColumns: [
        { key: 'courseName', title: '课程' },
        { key: 'className', title: '班级' },
        { key: 'teacherKey', title: '任课教师' },
        { key: 'status', title: '状态' },
        { key: 'progressRate', title: '录入进度' }
      ],
      examColumns: [
        { key: 'courseName', title: '课程' },
        { key: 'className', title: '班级' },
        { key: 'examDate', title: '考试日期' },
        { key: 'startTime', title: '开始' },
        { key: 'endTime', title: '结束' },
        { key: 'teacherName', title: '任课教师' }
      ],
      statusChangeColumns: [
        { key: 'studentName', title: '学生' },
        { key: 'changeTypeLabel', title: '异动类型' },
        { key: 'currentNode', title: '当前节点' },
        { key: 'status', title: '状态' },
        { key: 'submittedAt', title: '提交时间' }
      ],
      warningColumns: [
        { key: 'studentName', title: '学生' },
        { key: 'level', title: '等级' },
        { key: 'reason', title: '原因' },
        { key: 'status', title: '状态' }
      ],
      graduationColumns: [
        { key: 'studentName', title: '学生' },
        { key: 'batchName', title: '批次' },
        { key: 'overall', title: '系统判定' },
        { key: 'conclusion', title: '结论' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  computed: {
    termSubtitle() {
      if (this.currentTerm && this.currentTerm.termId) {
        return `当前学期：${this.currentTerm.yearCode} 第 ${this.currentTerm.termNo} 学期`
      }
      return '尚未设置当前学期 · 教务过程从「学年学期」开始'
    },
    gradeSubmittedCount() {
      const c = this.gradeProgress.counts || {}
      return (c.SUBMITTED || 0) + (c.ACADEMIC_REVIEW || 0) + (c.PUBLISHED || 0)
    },
    todayTeachingSubtitle() {
      const t = this.todayTeaching
      const parts = [t.dateLabel || '']
      if (t.termLabel) parts.push(t.termLabel + (t.weekNo ? `第 ${t.weekNo} 教学周` : ''))
      return parts.filter(Boolean).join(' · ')
    },
    trendRows() {
      return (this.dataTrends.series || []).flatMap((s) => (s.points || []).map((p) => ({
        date: p.date, series: s.label, value: p.value
      })))
    },
    trendHasData() {
      return (this.dataTrends.series || []).some((s) => (s.points || []).some((p) => p.value > 0))
    },
    trendChartSpec() {
      return {
        type: 'line',
        data: this.trendRows,
        encode: { x: 'date', y: 'value', color: 'series' },
        shape: 'smooth',
        style: { lineWidth: 2.5, point: true },
        legend: { color: { position: 'bottom' } }
      }
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.$nextTick(() => this.scrollToPanel(panel))
      }
    }
  },
  created() {
    this.load()
    this.loadReminders()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    termRange(t) {
      if (t.startDate && t.endDate) return `${t.startDate} ~ ${t.endDate}`
      return '起止日期未设置'
    },
    runStatusTagType(status) {
      return RUN_STATUS_TYPE[status] || 'default'
    },
    formatSlots(slots) {
      return (slots || []).map((s) => `第${s}节`).join('、') || '-'
    },
    scrollToPanel(panel) {
      const id = PANEL_ANCHORS[(panel || '').toString()]
      if (!id) return
      const el = document.getElementById(id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    },
    async loadReminders() {
      this.remindersLoading = true
      this.remindersError = ''
      const res = await academicAffairsApi.getDashboardReminders()
      if (res.code === 0) {
        const d = res.data || {}
        this.gradeProgress = d.gradeProgress || {}
        this.examReminders = d.examReminders || {}
        this.statusChangeReminders = d.statusChangeReminders || {}
        this.warningReminders = d.warningReminders || {}
        this.graduationWarnings = d.graduationWarnings || {}
        this.todos = d.todos || []
        this.todayTeaching = d.todayTeaching || {}
        this.todayCourses = d.todayCourses || {}
        this.scheduleChangeReminders = d.scheduleChangeReminders || {}
        this.resourceOccupancy = d.resourceOccupancy || {}
        this.dataTrends = d.dataTrends || {}
      } else {
        this.remindersError = res.message
      }
      this.remindersLoading = false
      this.$nextTick(() => this.scrollToPanel(this.$route.query.panel))
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
.aa-todo-row {
  align-items: center;
}
.aa-more-hint {
  color: var(--text-500, #646a73);
  font-size: 12px;
  text-align: center;
  padding-top: 4px;
}
</style>
