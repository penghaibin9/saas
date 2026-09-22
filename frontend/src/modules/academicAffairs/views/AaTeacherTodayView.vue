<template>
  <ModulePageShell
    title="今日教学"
    subtitle="今天该做什么一眼看清；所有数字和课次都来自本人正式教学事实"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton @click="go('/admin/academic-affairs/schedule/teacher')">查看完整课表</AppButton>
      <AppButton variant="primary" :loading="loading" @click="load">刷新</AppButton>
    </template>

    <AppInlineAlert
      v-if="warnings.length"
      type="warning"
      title="部分待办暂未读取成功"
      :description="`未读取成功的项目：${warnings.join('、')}。页面不会把接口失败显示成 0；可点击刷新重试。`"
    />

    <section class="aat-metrics" aria-label="我的今日教学摘要">
      <button v-for="metric in metrics" :key="metric.key" type="button" class="aat-metric" @click="go(metric.path)">
        <small>{{ metric.label }}</small>
        <strong>{{ metric.value == null ? '—' : metric.value }}</strong>
        <span>{{ metric.unit }}</span>
      </button>
    </section>

    <div class="aat-grid">
      <AppSectionCard title="今天的课">
        <div class="aat-card-head">
          <span>{{ todayDate || '今天' }}<template v-if="todayWeek"> · 第{{ todayWeek }}教学周</template></span>
          <small>{{ todayNote }}</small>
        </div>
        <LoadingState v-if="loading && !loadedOnce" />
        <ErrorState v-else-if="todayError" :description="todayError" @retry="load" />
        <div v-else-if="todayItems.length" class="aat-course-list">
          <article v-for="item in todayItems" :key="item.scheduleItemId || item.itemId" class="aat-course">
            <div class="aat-slot"><strong>第{{ item.slotNo }}节</strong><span>{{ item.timeText || '按正式作息' }}</span></div>
            <div class="aat-course-main">
              <strong>{{ item.courseName || '课程待核对' }}</strong>
              <span>{{ item.className || item.teachingClassName || '教学班待核对' }} · {{ item.classroom || '教室待定' }}</span>
            </div>
            <div class="aat-course-actions">
              <AppButton size="small" @click="go('/admin/academic-affairs/attendance-stats?panel=sessions')">考勤查询</AppButton>
              <AppButton size="small" variant="primary" @click="applyChange(item)">调停课</AppButton>
            </div>
          </article>
        </div>
        <EmptyState v-else title="今天没有授课安排" :description="todayNote" />
        <p class="aat-footnote">逐生点名写入仍由教师移动端正式考勤入口负责；PC 此处只进入本人考勤查询，避免制造第二套点名写链。</p>
      </AppSectionCard>

      <AppSectionCard title="我的待办">
        <LoadingState v-if="loading && !loadedOnce" />
        <template v-else-if="todoRows.length">
          <div v-for="item in todoRows" :key="item.key" class="aat-todo">
            <div><strong>{{ item.title }}</strong><span>{{ item.note }}</span></div>
            <AppButton size="small" :variant="item.primary ? 'primary' : 'default'" @click="go(item.path)">{{ item.action }}</AppButton>
          </div>
        </template>
        <EmptyState v-else title="当前没有待处理事项" description="已读取本人教学任务、成绩、调停课、教材和预约状态。" />
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard } from '@/components/common'
import {
  academicAffairsApi,
  academicAffairsTextbookApi,
  academicAffairsClassroomBookingApi,
  academicAffairsLabBookingApi
} from '@/modules/academicAffairs/api/academic-affairs.api'
import { scheduleChangeApi } from '@/modules/academicAffairs/api/academic-schedule-change.api'

const ACTIVE_CHANGE = new Set(['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW', 'APPROVED'])
const ACTION_GRADE = new Set(['DRAFT', 'INPUTTING', 'RETURNED', 'COLLEGE_RETURNED'])
const ACTION_TEXTBOOK = new Set(['DRAFT', 'RETURNED'])

function list(res) { return res?.code === 0 ? (res.data?.list || res.data?.items || []) : [] }

export default {
  name: 'AaTeacherTodayView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, loadedOnce: false, generation: 0,
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', todayError: '',
      taskRows: null, gradeRows: null, changeRows: null, textbookRows: null, bookingRows: null,
      warnings: []
    }
  },
  computed: {
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
      if (this.calendarSource === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '来自本人正式课表与校历课次投影。' : '已核对校历与本人正式课表。'
    },
    pendingGradeRows() {
      return (this.gradeRows || []).filter(row =>
        (row.allowedActions || []).some(action => ['INPUT', 'SUBMIT'].includes(action)) ||
        ACTION_GRADE.has(String(row.status || '').toUpperCase()))
    },
    pendingChangeRows() {
      return (this.changeRows || []).filter(row => ACTIVE_CHANGE.has(String(row.status || '').toUpperCase()))
    },
    attentionTextbookRows() {
      return (this.textbookRows || []).filter(row => ACTION_TEXTBOOK.has(String(row.status || '').toUpperCase()))
    },
    pendingBookings() {
      return (this.bookingRows || []).filter(row => String(row.status || '').toUpperCase() === 'PENDING')
    },
    metrics() {
      return [
        { key: 'today', label: '今日课程', value: this.todayError ? null : this.todayItems.length, unit: '节', path: '/admin/academic-affairs/schedule/teacher' },
        { key: 'task', label: '待确认教学任务', value: this.taskRows == null ? null : this.taskRows.length, unit: '项', path: '/admin/academic-affairs/teaching-tasks/teacher-confirm' },
        { key: 'grade', label: '待录入成绩', value: this.gradeRows == null ? null : this.pendingGradeRows.length, unit: '门', path: '/admin/academic-affairs/grade-entry' },
        { key: 'change', label: '调停课审核中', value: this.changeRows == null ? null : this.pendingChangeRows.length, unit: '条', path: '/admin/academic-affairs/schedule-change' },
        { key: 'resource', label: '教材/预约待处理', value: this.textbookRows == null || this.bookingRows == null ? null : this.attentionTextbookRows.length + this.pendingBookings.length, unit: '项', path: '/admin/academic-affairs/textbooks?tab=selection' }
      ]
    },
    todoRows() {
      const rows = []
      const task = (this.taskRows || [])[0]
      if (task) rows.push({ key: `task-${task.taskId}`, title: `确认《${task.courseName || '教学任务'}》`, note: [task.className, task.teachingClassName, '学院已分配'].filter(Boolean).join(' · '), action: '去确认', primary: true, path: '/admin/academic-affairs/teaching-tasks/teacher-confirm' })
      const grade = this.pendingGradeRows[0]
      if (grade) rows.push({ key: `grade-${grade.gradeTaskId || grade.taskId}`, title: `录入《${grade.courseName || '课程'}》成绩`, note: [grade.className, grade.status].filter(Boolean).join(' · '), action: '继续录入', path: '/admin/academic-affairs/grade-entry' })
      const textbook = this.attentionTextbookRows[0]
      if (textbook) rows.push({ key: `textbook-${textbook.selectionId}`, title: `教材选用${textbook.status === 'RETURNED' ? '被退回' : '待提交'}`, note: textbook.courseName || `申报 ${textbook.selectionId}`, action: '去处理', path: '/admin/academic-affairs/textbooks?tab=selection' })
      const booking = this.pendingBookings[0]
      if (booking) rows.push({ key: `booking-${booking.bookingId}`, title: '教学资源预约待审核', note: [booking.classroomText || booking.labText, booking.bookingDate, booking.slotNo ? `第${booking.slotNo}节` : ''].filter(Boolean).join(' · '), action: '查看', path: booking.labText ? '/admin/academic-affairs/resources/lab-bookings' : '/admin/academic-affairs/classroom-bookings' })
      const change = this.pendingChangeRows[0]
      if (change && rows.length < 5) rows.push({ key: `change-${change.changeId}`, title: `调停课申请：${change.courseName || '课程'}`, note: change.statusLabel || change.status || '审核中', action: '查看进度', path: '/admin/academic-affairs/schedule-change' })
      return rows.slice(0, 5)
    }
  },
  created() { this.load() },
  beforeUnmount() { this.generation++ },
  methods: {
    go(path) { this.$router.push(path).catch(() => {}) },
    applyChange(item) {
      const originItemId = item.scheduleItemId || item.itemId
      if (!originItemId) return
      this.$router.push({ path: '/admin/academic-affairs/schedule-change/apply', query: { originItemId: String(originItemId), changeType: 'ADJUST' } }).catch(() => {})
    },
    async load() {
      const ticket = ++this.generation
      this.loading = true
      this.warnings = []
      const calls = [
        ['今日课表', () => academicAffairsApi.getMyTeacherToday()],
        ['教学任务', () => academicAffairsApi.listAllTasks({ mine: true, status: 'ASSIGNED', page: 1, pageSize: 100 })],
        ['成绩任务', () => academicAffairsApi.getGradeTasks({ page: 1, pageSize: 100 })],
        ['调停课', () => scheduleChangeApi.list({ page: 1, pageSize: 100 })],
        ['教材选用', () => academicAffairsTextbookApi.listSelections({ page: 1, pageSize: 100 })],
        ['教室预约', () => academicAffairsClassroomBookingApi.list({ page: 1, pageSize: 100 })],
        ['实训室预约', () => academicAffairsLabBookingApi.list({ page: 1, pageSize: 100 })]
      ]
      const results = await Promise.all(calls.map(async ([label, run]) => {
        try { return [label, await run()] } catch (error) { return [label, { code: 1, message: error?.message || '读取失败' }] }
      }))
      if (ticket !== this.generation) return
      const by = Object.fromEntries(results)
      const today = by['今日课表']
      if (today?.code === 0) {
        this.todayItems = today.data?.todayItems || []
        this.todayDate = today.data?.todayDate || ''
        this.todayWeek = today.data?.currentWeek ?? null
        this.calendarSource = today.data?.calendarSource || ''
        this.todayError = ''
      } else {
        this.todayItems = []; this.todayError = today?.message || '今日课表读取失败'; this.warnings.push('今日课表')
      }
      const assign = (label, key) => {
        const res = by[label]
        if (res?.code === 0) this[key] = list(res)
        else { this[key] = null; this.warnings.push(label) }
      }
      assign('教学任务', 'taskRows')
      assign('成绩任务', 'gradeRows')
      assign('调停课', 'changeRows')
      assign('教材选用', 'textbookRows')
      const classroom = by['教室预约'], lab = by['实训室预约']
      if (classroom?.code === 0 && lab?.code === 0) this.bookingRows = [...list(classroom), ...list(lab)]
      else { this.bookingRows = null; if (classroom?.code !== 0) this.warnings.push('教室预约'); if (lab?.code !== 0) this.warnings.push('实训室预约') }
      this.loadedOnce = true
      this.loading = false
    }
  }
}
</script>

<style scoped>
.aat-metrics { display:grid; grid-template-columns:repeat(5,minmax(120px,1fr)); gap:10px; }
.aat-metric { min-height:78px; padding:13px 14px; border:1px solid var(--border-base); border-radius:10px; background:var(--bg-card); text-align:left; color:inherit; }
.aat-metric:hover { border-color:var(--pri); background:var(--pri-bg); }
.aat-metric small { display:block; color:var(--text-secondary); font-size:11px; }
.aat-metric strong { display:inline-block; margin-top:7px; font-size:24px; line-height:1; }
.aat-metric span { margin-left:4px; color:var(--text-tertiary); font-size:11px; }
.aat-grid { display:grid; grid-template-columns:minmax(0,1.45fr) minmax(320px,.8fr); gap:12px; align-items:start; }
.aat-card-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:8px; color:var(--text-secondary); font-size:11px; }
.aat-course { display:grid; grid-template-columns:80px minmax(0,1fr) auto; gap:12px; align-items:center; padding:11px 0; border-bottom:1px solid var(--border-base); }
.aat-course:last-child { border-bottom:0; }
.aat-slot strong,.aat-slot span,.aat-course-main strong,.aat-course-main span { display:block; }
.aat-slot strong,.aat-course-main strong { font-size:13px; color:var(--text-primary); }
.aat-slot span,.aat-course-main span { margin-top:3px; color:var(--text-secondary); font-size:11px; }
.aat-course-actions { display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
.aat-todo { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:11px 0; border-bottom:1px solid var(--border-base); }
.aat-todo:last-child { border-bottom:0; }
.aat-todo strong,.aat-todo span { display:block; }
.aat-todo strong { color:var(--text-primary); font-size:12px; }
.aat-todo span { margin-top:3px; color:var(--text-secondary); font-size:11px; }
.aat-footnote { margin:12px 0 0; color:var(--text-tertiary); font-size:11px; line-height:1.6; }
@container academic-body (max-width:1000px) { .aat-metrics{grid-template-columns:repeat(3,minmax(120px,1fr))}.aat-grid{grid-template-columns:1fr} }
@container academic-body (max-width:640px) { .aat-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.aat-course{grid-template-columns:1fr}.aat-course-actions{justify-content:flex-start} }
</style>
