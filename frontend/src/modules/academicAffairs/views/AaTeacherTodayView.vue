<template>
  <ModulePageShell
    title="今日教学"
    subtitle="当前学期、本人正式任课关系、正式课表与业务待办一次读清"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton @click="go('/admin/academic-affairs/schedule/teacher')">查看完整课表</AppButton>
      <AppButton variant="primary" :loading="loading" @click="refresh">刷新</AppButton>
    </template>

    <AppInlineAlert
      v-if="workbenchSource && workbenchSource !== 'CURRENT_TERM_FORMAL_TEACHER_FACTS'"
      type="warning"
      title="工作台事实来源待核对"
      description="正式教学事实来源暂未确认，请刷新后核对；不要据此重复办理。"
    />

    <section v-if="isAcademicTeacher" class="aat-responsibility" aria-label="我的学期责任">
      <template v-if="flowTermError">
        <AppInlineAlert type="warning" :description="flowTermError" />
        <AppButton @click="selectFlowTerm('')">恢复当前学期</AppButton>
      </template>
      <AcademicFlowOverview v-else ref="responsibilityFlow" :ctx="ctx" :term-id="flowTermId" :can-open="canOpenFlow" @navigate="openFlow" @term-change="selectFlowTerm" />
      <p v-if="flowTermId" class="aat-footnote">责任进度按所选学期查看；下方今日课程与待办仍按当前学期查询。</p>
    </section>

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
        <LoadingState v-if="loading" />
        <ErrorState v-else-if="todayError" :description="todayError" @retry="load" />
        <div v-else-if="todayItems.length" class="aat-course-list">
          <article v-for="item in todayItems" :key="item.scheduleItemId || item.itemId" class="aat-course">
            <div class="aat-slot"><strong>第{{ item.slotNo }}节</strong><span>{{ item.timeText || '按正式作息' }}</span></div>
            <div class="aat-course-main">
              <strong>{{ item.courseName || '课程待核对' }}</strong>
              <span>{{ item.className || item.teachingClassName || '教学班待核对' }} · {{ item.classroom || '教室待定' }}</span>
            </div>
            <div class="aat-course-actions">
              <AppButton v-if="item.attendanceExecutable" size="small" :loading="attendanceOpeningId === String(item.scheduleItemId)" @click="openAttendance(item)">考勤</AppButton>
              <AppButton v-else size="small" @click="go('/admin/academic-affairs/attendance-stats?panel=sessions')">考勤查询</AppButton>
              <AppButton size="small" variant="primary" @click="applyChange(item)">调课</AppButton>
            </div>
          </article>
        </div>
        <EmptyState v-else title="今天没有授课安排" :description="todayNote" />
        <p class="aat-footnote">PC 与教师移动端共用同一课堂考勤场次、正式名单、提交状态和预警写链，不再存在第二套点名事实。</p>
      </AppSectionCard>

      <AppSectionCard title="我的待办">
        <LoadingState v-if="loading" />
        <ErrorState v-else-if="todayError" :description="todayError" @retry="load" />
        <template v-else>
          <div class="aat-work-tabs" role="tablist" aria-label="我的待办状态">
            <button type="button" :class="{ active: workTab === 'actions' }" @click="workTab = 'actions'">待我处理 <b>{{ actionItems.length }}</b></button>
            <button type="button" :class="{ active: workTab === 'waiting' }" @click="workTab = 'waiting'">办理中 <b>{{ waitingItems.length }}</b></button>
          </div>
          <template v-if="workTab === 'actions'">
            <template v-if="actionItems.length">
              <div v-for="item in actionItems" :key="`action-${item.kind}-${item.id}`" class="aat-todo">
                <div><strong>{{ item.title }}</strong><span>{{ item.note }}</span></div>
                <AppButton size="small" :variant="item.primary ? 'primary' : 'default'" @click="go(item.path)">{{ item.action || '去处理' }}</AppButton>
              </div>
            </template>
            <EmptyState v-else title="当前没有需要本人处理的事项" description="当前学期需要您本人办理的任务已经处理完。" />
          </template>
          <template v-else>
            <template v-if="waitingItems.length">
              <div v-for="item in waitingItems" :key="`waiting-${item.kind}-${item.id}`" class="aat-todo">
                <div><strong>{{ item.title }}</strong><span>{{ item.note }}</span></div>
                <AppButton size="small" @click="go(item.path)">{{ item.action || '查看进度' }}</AppButton>
              </div>
            </template>
            <EmptyState v-else title="当前没有办理中事项" description="提交学院、教务或资源管理员的事项会在这里持续显示进度。" />
          </template>
        </template>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { canEnterRoute } from '@/security/permissionGate'
import { currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext.js'
import AcademicFlowOverview from '../components/AcademicFlowOverview.vue'
import { normalizeUiError } from '@/utils/presentationSafety'

const EMPTY_WORKBENCH = () => ({
  actionItems: [], waitingItems: [],
  counts: { actions: 0, waiting: 0, teachingTasks: 0, grades: 0, textbooks: 0, scheduleChanges: 0, bookings: 0 },
  source: ''
})

export default {
  name: 'AaTeacherTodayView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AcademicFlowOverview },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, generation: 0, attendanceOpeningId: '', disposed: false,
      workTab: this.$route?.query?.work === 'waiting' ? 'waiting' : 'actions',
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', todayError: '',
      workbench: EMPTY_WORKBENCH()
    }
  },
  computed: {
    isAcademicTeacher() { return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER' },
    identityKey() { return JSON.stringify([academicIdentity(currentUserFromToken(), this.ctx), this.ctx.currentRole]) },
    flowTermId() { return typeof this.$route.query.termId === 'string' ? this.$route.query.termId : '' },
    flowTermError() { const value = this.$route.query.termId; return value != null && (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) ? '学期参数无效，请恢复当前学期后重新选择。' : '' },
    workbenchSource() { return this.workbench?.source || '' },
    actionItems() { return this.workbench?.actionItems || [] },
    waitingItems() { return this.workbench?.waitingItems || [] },
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
      if (this.calendarSource === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '来自本人正式课表、正式任课关系与校历课次投影。' : '已核对校历与本人正式课表。'
    },
    metrics() {
      const c = this.workbench?.counts || {}
      const firstPath = kinds => [...this.actionItems, ...this.waitingItems].find(item => kinds.includes(item.kind))?.path
      return [
        { key: 'today', label: '今日课程', value: this.todayError ? null : this.todayItems.length, unit: '节', path: '/admin/academic-affairs/schedule/teacher' },
        { key: 'task', label: '待确认任务', value: this.todayError ? null : Number(c.teachingTasks || 0), unit: '项', path: firstPath(['TEACHING_TASK']) || '/admin/academic-affairs/teaching-tasks/teacher-confirm' },
        { key: 'grade', label: '待录成绩', value: this.todayError ? null : Number(c.grades || 0), unit: '门', path: firstPath(['GRADE', 'GRADE_SETUP']) || '/admin/academic-affairs/grade-entry' },
        { key: 'change', label: '调停课审核中', value: this.todayError ? null : Number(c.scheduleChanges || 0), unit: '条', path: firstPath(['SCHEDULE_CHANGE']) || '/admin/academic-affairs/schedule-change' },
        { key: 'materials', label: '教材/预约', value: this.todayError ? null : Number(c.textbooks || 0) + Number(c.bookings || 0), unit: '项', path: firstPath(['TEXTBOOK', 'CLASSROOM_BOOKING', 'LAB_BOOKING']) || '/admin/academic-affairs/textbooks?tab=selection' }
      ]
    }
  },
  created() { this.load() },
  watch: {
    identityKey() { this.generation++; this.attendanceOpeningId = ''; this.load() },
    '$route.query.work'(value) {
      this.workTab = value === 'waiting' ? 'waiting' : 'actions'
    }
  },
  beforeUnmount() { this.generation++; this.disposed = true },
  methods: {
    refresh() { this.$refs.responsibilityFlow?.load(); return this.load() },
    canOpenFlow(path) { try { const route = this.$router.resolve(path); return Boolean(route.matched?.length) && route.matched.every(row => canEnterRoute(row.meta)) } catch { return false } },
    openFlow(path) { if (this.canOpenFlow(path)) this.go(path) },
    selectFlowTerm(value) {
      const termId = value == null ? '' : String(value)
      if (termId && !/^[1-9]\d*$/.test(termId)) return
      return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: termId || undefined } })
    },
    go(path) { if (path) this.$router.push(path).catch(() => {}) },
    applyChange(item) {
      const originItemId = item.scheduleItemId || item.itemId
      if (!originItemId) return
      this.$router.push({
        path: '/admin/academic-affairs/schedule-change/apply',
        query: { originItemId: String(originItemId), changeType: 'ADJUST', occurrenceWeek: String(item.weekNo || this.todayWeek || '') }
      }).catch(() => {})
    },
    async openAttendance(item) {
      const scheduleItemId = String(item.scheduleItemId || '')
      if (!scheduleItemId || this.attendanceOpeningId) return
      this.attendanceOpeningId = scheduleItemId
      const identity = this.identityKey
      try {
        const res = await academicAffairsApi.openAttendanceSession({
          teachingTaskId: String(item.teachingTaskId),
          classId: item.classId ? String(item.classId) : undefined,
          sessionDate: item.sessionDate || this.todayDate,
          slotNo: Number(item.slotNo),
          scheduleItemId
        })
        if (this.disposed || identity !== this.identityKey) return
        if (res.code !== 0 || !res.data?.sessionId) {
          toast.error(res.message || '课堂考勤场次未确认，请刷新后重试')
          return
        }
        this.go(`/admin/academic-affairs/attendance-stats?panel=sessions&sessionId=${encodeURIComponent(res.data.sessionId)}`)
      } catch (error) {
        if (!this.disposed && identity === this.identityKey) toast.error(error?.message || '课堂考勤场次未确认，请刷新后重试')
      } finally { if (!this.disposed && identity === this.identityKey) this.attendanceOpeningId = '' }
    },
    async load() {
      const ticket = ++this.generation, identity = this.identityKey
      const current = () => !this.disposed && ticket === this.generation && identity === this.identityKey
      this.loading = true
      this.todayItems = []; this.workbench = EMPTY_WORKBENCH(); this.todayDate = ''; this.todayWeek = null; this.calendarSource = ''; this.todayError = ''
      try {
        const res = await academicAffairsApi.getMyTeacherToday()
        if (!current()) return
        if (res.code !== 0) {
          this.todayItems = []; this.workbench = EMPTY_WORKBENCH(); this.todayError = normalizeUiError(res, { fallback: '今日教学暂时无法读取，请重试' }).userMessage
          return
        }
        const data = res.data || {}
        this.todayItems = data.todayItems || []
        this.todayDate = data.todayDate || ''
        this.todayWeek = data.currentWeek ?? null
        this.calendarSource = data.calendarSource || ''
        this.todayError = ''
        this.workbench = { ...EMPTY_WORKBENCH(), ...(data.workbench || {}), counts: { ...EMPTY_WORKBENCH().counts, ...(data.workbench?.counts || {}) } }
      } catch (error) {
        if (!current()) return; this.todayItems = []; this.workbench = EMPTY_WORKBENCH(); this.todayError = normalizeUiError(error, { fallback: '今日教学暂时无法读取，请重试' }).userMessage
      } finally { if (current()) this.loading = false }
    }
  }
}
</script>
<style scoped>
.aat-responsibility { display:grid; gap:12px; margin-bottom:16px; }
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
.aat-work-tabs { display:flex; gap:6px; padding:0 0 10px; border-bottom:1px solid var(--border-base); margin-bottom:4px; }
.aat-work-tabs button { border:0; border-radius:7px; padding:7px 10px; background:transparent; color:var(--text-secondary); cursor:pointer; font-size:12px; }
.aat-work-tabs button.active { background:var(--pri-bg); color:var(--pri); font-weight:600; }
.aat-work-tabs b { margin-left:4px; font-size:11px; }
.aat-waiting-head { margin-top:16px; padding-top:14px; border-top:1px solid var(--border-base); }
.aat-footnote { margin:12px 0 0; color:var(--text-tertiary); font-size:11px; line-height:1.6; }
@container academic-body (max-width:1000px) { .aat-metrics{grid-template-columns:repeat(3,minmax(120px,1fr))}.aat-grid{grid-template-columns:1fr} }
@container academic-body (max-width:640px) { .aat-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.aat-course{grid-template-columns:1fr}.aat-course-actions{justify-content:flex-start} }
</style>
