<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '考勤详情' : '课堂考勤'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <view class="section-head">
          <text class="section-head__title">我的考勤场次</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新建场次' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="taskLabels" :value="taskIndex" @change="onTaskPick">
            <view class="at__input at__date">{{ taskLabels[taskIndex] || '选择当前教学任务（必填）' }}</view>
          </picker>
          <view v-if="selectedTask" class="at__task-note">
            <text>{{ selectedTask.courseName || '未命名课程' }}</text>
            <text>{{ selectedTask.className || '未关联班级' }} · {{ selectedTask.termCode || '当前学期' }}</text>
          </view>
          <picker mode="date" :value="form.sessionDate" @change="onDateChange">
            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>
          </picker>
          <input class="at__input" type="number" v-model="form.slotNo" placeholder="第几节（选填）" placeholder-class="at__ph" />
          <picker mode="selector" :range="sessionTypes" @change="onTypeChange">
            <view class="at__input at__date">点名类别：{{ form.sessionType || '常规' }}</view>
          </picker>
          <button class="btn btn-primary" :disabled="!form.teachingTaskId || !form.sessionDate || creating" @click="createSession">
            {{ creating ? '创建中…' : '按教学任务圈定名单并新建' }}
          </button>
          <text v-if="!taskOptions.length" class="at__sub">暂无可用教学任务：请确认当前学期教学任务已分配到本人并完成教师确认。</text>
        </view>

        <MobileGlobalState v-if="!sessions.length" state="empty" title="暂无考勤场次" description="点击右上角新建场次。" />
        <view class="list-group" v-else>
          <view v-for="session in sessions" :key="session.sessionId" class="list-row" @click="openSession(session)">
            <view class="flex-1">
              <text class="t-md">{{ session.courseName || '（未命名课程）' }}</text>
              <text class="at__sub">{{ session.sessionDate }}{{ session.slotNo ? ' 第' + session.slotNo + '节' : '' }} · 出勤 {{ session.presentCount }}/{{ session.totalCount }}</text>
            </view>
            <MobileStatusTag :status="session.status" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <text class="at__back" @click="closeSession">‹ 返回场次列表</text>
        <view class="card row-between">
          <text class="t-md t-bold">{{ active.courseName || '（未命名课程）' }}</text>
          <MobileStatusTag :status="active.status" />
        </view>

        <MobileGlobalState v-if="detailLoading" state="loading" title="正在读取本场考勤名单" />
        <template v-else>
          <MobileGlobalState v-if="!items.length" state="empty" title="本场暂无学生名单" description="请检查教学任务正式名单是否已锁定。" />
          <view class="list-group" v-else>
            <view v-for="item in items" :key="item.studentId" class="list-row at__row">
              <view class="flex-1">
                <text class="t-md">{{ item.realName }}</text>
                <text class="at__sub">{{ item.studentNo }}</text>
              </view>
              <view class="at__seg" :class="{ 'is-pending': marking[item.studentId] }">
                <text
                  v-for="option in STATUS_OPTS" :key="option.value"
                  class="at__seg-item" :class="{ 'is-active': item.status === option.value }"
                  @click="active.status === 'DRAFT' && mark(item, option.value)"
                >{{ option.label }}</text>
              </view>
            </view>
          </view>
        </template>

        <MobileSafeAreaBar v-if="!detailLoading && active.status === 'DRAFT' && items.length">
          <button class="btn btn-primary flex-1" :disabled="submitting || hasPendingMarks" @click="submitSession">
            {{ submitting ? '提交中…' : hasPendingMarks ? '正在保存标记…' : '提交考勤（提交后不可再改）' }}
          </button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const STATUS_OPTS = [
  { value: 'PRESENT', label: '出勤' },
  { value: 'LATE', label: '迟到' },
  { value: 'ABSENT', label: '缺勤' },
  { value: 'LEAVE', label: '请假' }
]
const ALLOWED_TASK_STATUSES = new Set(['TEACHER_CONFIRMED', 'COLLEGE_REVIEW', 'APPROVED'])

export default {
  data() {
    return {
      sessions: [], loaded: false, state: 'loading', showForm: false, creating: false,
      sessionTypes: ['常规', '实训', '晚自习', '其他'],
      taskOptions: [], taskIndex: 0,
      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', sessionType: '' },
      active: null, items: [], detailLoading: false, marking: {}, submitting: false, STATUS_OPTS
    }
  },
  computed: {
    taskLabels() {
      return (this.taskOptions || []).map((task) => `${task.courseName || '未命名课程'} · ${task.className || '未关联班级'}`)
    },
    selectedTask() {
      return (this.taskOptions || [])[this.taskIndex] || null
    },
    hasPendingMarks() {
      return Object.values(this.marking).some(Boolean)
    }
  },
  onLoad() { this.load(); this.loadTasks() },
  methods: {
    onDateChange(event) { this.form.sessionDate = event.detail.value },
    onTypeChange(event) { this.form.sessionType = this.sessionTypes[Number(event.detail.value)] || '' },
    applyTask(task) {
      this.form.teachingTaskId = task ? task.teachingTaskId : ''
      this.form.classId = task ? task.classId : ''
    },
    onTaskPick(event) {
      this.taskIndex = Number(event.detail.value)
      this.applyTask(this.taskOptions[this.taskIndex])
    },
    confirmModal(title, content, confirmText = '确定') {
      return new Promise((resolve) => {
        uni.showModal({
          title, content, confirmText, cancelText: '取消',
          success: (result) => resolve(!!result.confirm),
          fail: () => resolve(false)
        })
      })
    },
    loadTasks() {
      teacherApi.getAttendanceClassOptions().then((data) => {
        this.taskOptions = ((data && data.items) || []).filter((task) =>
          ALLOWED_TASK_STATUSES.has(String(task.taskStatus || '').toUpperCase()))
        this.taskIndex = 0
        this.applyTask(this.taskOptions[0])
      }).catch(() => {
        this.taskOptions = []
        this.applyTask(null)
      })
    },
    load() {
      this.state = 'loading'
      teacherApi.getAttendanceSessions().then((data) => {
        this.sessions = (data && data.items) || []
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    createSession() {
      if (this.creating || !this.form.teachingTaskId || !this.form.sessionDate) return
      this.creating = true
      teacherApi.createAttendanceSession({
        teachingTaskId: Number(this.form.teachingTaskId),
        classId: this.form.classId ? Number(this.form.classId) : undefined,
        sessionDate: this.form.sessionDate,
        slotNo: this.form.slotNo ? Number(this.form.slotNo) : undefined,
        sessionType: this.form.sessionType || undefined
      }).then(() => {
        uni.showToast({ title: '考勤场次已创建', icon: 'success' })
        this.showForm = false
        this.form.sessionDate = ''
        this.form.slotNo = ''
        this.form.sessionType = ''
        this.applyTask(this.taskOptions[this.taskIndex])
        this.load()
      }).catch((error) => toast(error && error.biz ? normalizeError(error).text : '创建失败，请稍后重试'))
        .finally(() => { this.creating = false })
    },
    closeSession() {
      if (this.hasPendingMarks) {
        toast('仍有考勤标记正在保存，请稍候')
        return
      }
      this.active = null
      this.items = []
      this.marking = {}
      this.detailLoading = false
    },
    openSession(session) {
      this.active = { ...session }
      this.items = []
      this.marking = {}
      this.detailLoading = true
      teacherApi.getAttendanceDetail(session.sessionId).then((data) => {
        this.active = data
        this.items = (data && data.items) || []
      }).catch((error) => {
        this.active = null
        this.items = []
        this.marking = {}
        toast(error && error.biz ? normalizeError(error).text : '名单加载失败，请稍后重试')
      }).finally(() => { this.detailLoading = false })
    },
    mark(item, status) {
      const studentId = item.studentId
      if (this.detailLoading || this.marking[studentId] || item.status === status) return
      const previous = item.status
      item.status = status
      this.marking[studentId] = true
      teacherApi.markAttendance(this.active.sessionId, studentId, status).then((data) => {
        this.active.presentCount = data.presentCount
        this.active.absentCount = data.absentCount
      }).catch((error) => {
        item.status = previous
        toast(error && error.biz ? normalizeError(error).text : '标记失败，请稍后重试')
      }).finally(() => { this.marking[studentId] = false })
    },
    async submitSession() {
      if (this.submitting || this.detailLoading || this.hasPendingMarks || !this.active || !this.items.length) return
      const confirmed = await this.confirmModal(
        '提交本场考勤',
        `即将提交${this.active.courseName || '本课程'}共${this.items.length}人的考勤结果。提交后教师端不可直接修改，确认继续？`,
        '确认提交'
      )
      if (!confirmed) return
      this.submitting = true
      teacherApi.submitAttendanceSession(this.active.sessionId).then(() => {
        uni.showToast({ title: '考勤已提交', icon: 'success' })
        this.active = null
        this.items = []
        this.marking = {}
        this.load()
      }).catch((error) => toast(error && error.biz ? normalizeError(error).text : '提交失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.at__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.at__date { color: var(--text-primary); }
.at__ph { color: var(--text-tertiary); }
.at__task-note { display: flex; flex-direction: column; gap: 3px; padding: var(--space-3); border-radius: var(--radius-md); background: var(--teacher-50); color: var(--text-secondary); font-size: var(--font-size-xs); }
.at__task-note text:first-child { color: var(--teacher-700); font-size: var(--font-size-sm); font-weight: 600; }
.at__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.at__back { display: inline-block; font-size: var(--font-size-sm); color: var(--brand-primary); margin-bottom: var(--space-3); }
.at__row { align-items: center; }
.at__seg { display: flex; flex-shrink: 0; border: 1px solid var(--border-base); border-radius: var(--radius-md); overflow: hidden; }
.at__seg.is-pending { opacity: .55; pointer-events: none; }
.at__seg-item { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 6px 8px; }
.at__seg-item.is-active { background: var(--brand-primary); color: #fff; }
</style>
