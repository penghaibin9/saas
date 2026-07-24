<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '考勤详情' : '课堂考勤'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <!-- 场次列表 -->
      <view class="page-pad" v-if="!active && loaded">
        <view class="section-head">
          <text class="section-head__title">我的考勤场次</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新建场次' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="classLabels" :value="classIndex" @change="onClassPick">
            <view class="at__input at__date">{{ classLabels[classIndex] || '选择行政班（必填）' }}</view>
          </picker>
          <input class="at__input" v-model="form.courseName" placeholder="课程名称" placeholder-class="at__ph" />
          <input class="at__input" v-model="form.termCode" placeholder="学期（选填）" placeholder-class="at__ph" />
          <picker mode="date" :value="form.sessionDate" @change="onDateChange">
            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>
          </picker>
          <input class="at__input" type="number" v-model="form.slotNo" placeholder="第几节（选填）" placeholder-class="at__ph" />
          <picker mode="selector" :range="sessionTypes" @change="onTypeChange">
            <view class="at__input at__date">点名类别：{{ form.sessionType || '常规' }}</view>
          </picker>
          <button class="btn btn-primary" :disabled="!form.classId || !form.sessionDate || creating" @click="createSession">
            {{ creating ? '创建中…' : '按行政班圈定名单并新建' }}
          </button>
          <text v-if="!classOptions.length" class="at__sub">暂无可选班级：请确认已绑定教学任务或辅导员/班主任班级。</text>
        </view>

        <MobileGlobalState v-if="!sessions.length" state="empty" title="暂无考勤场次" description="点击右上角新建场次。" />
        <view class="list-group" v-else>
          <view v-for="s in sessions" :key="s.sessionId" class="list-row" @click="openSession(s)">
            <view class="flex-1">
              <text class="t-md">{{ s.courseName || '（未命名课程）' }}</text>
              <text class="at__sub">{{ s.sessionDate }}{{ s.slotNo ? ' 第' + s.slotNo + '节' : '' }} · 出勤 {{ s.presentCount }}/{{ s.totalCount }}</text>
            </view>
            <MobileStatusTag :status="s.status" />
          </view>
        </view>
      </view>

      <!-- 场次详情 + 逐生标记 -->
      <view class="page-pad" v-if="active">
        <text class="at__back" @click="active = null">‹ 返回场次列表</text>
        <view class="card row-between">
          <text class="t-md t-bold">{{ active.courseName || '（未命名课程）' }}</text>
          <MobileStatusTag :status="active.status" />
        </view>
        <view class="list-group">
          <view v-for="it in items" :key="it.studentId" class="list-row at__row">
            <view class="flex-1">
              <text class="t-md">{{ it.realName }}</text>
              <text class="at__sub">{{ it.studentNo }}</text>
            </view>
            <view class="at__seg">
              <text
                v-for="opt in STATUS_OPTS" :key="opt.value"
                class="at__seg-item" :class="{ 'is-active': it.status === opt.value }"
                @click="active.status === 'DRAFT' && mark(it, opt.value)"
              >{{ opt.label }}</text>
            </view>
          </view>
        </view>

        <MobileSafeAreaBar v-if="active.status === 'DRAFT'">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitSession">
            {{ submitting ? '提交中…' : '提交考勤（提交后不可再改）' }}
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

export default {
  data() {
    return {
      sessions: [], loaded: false, state: 'loading', showForm: false, creating: false,
      sessionTypes: ['常规', '实训', '晚自习', '其他'],
      classOptions: [], classIndex: 0,
      form: { classId: '', courseName: '', termCode: '', sessionDate: '', slotNo: '', sessionType: '' },
      active: null, items: [], submitting: false, STATUS_OPTS
    }
  },
  computed: {
    classLabels() {
      return (this.classOptions || []).map((c) => `${c.className || '未命名班'}${c.grade ? ' · ' + c.grade : ''}`)
    }
  },
  onLoad() { this.load(); this.loadClasses() },
  methods: {
    onDateChange(e) { this.form.sessionDate = e.detail.value },
    onTypeChange(e) { this.form.sessionType = this.sessionTypes[Number(e.detail.value)] || '' },
    onClassPick(e) {
      this.classIndex = Number(e.detail.value)
      const c = this.classOptions[this.classIndex]
      this.form.classId = c ? c.classId : ''
    },
    loadClasses() {
      teacherApi.getAttendanceClassOptions().then((d) => {
        this.classOptions = (d && d.items) || []
        if (this.classOptions.length) {
          this.classIndex = 0
          this.form.classId = this.classOptions[0].classId
        }
      }).catch(() => { this.classOptions = [] })
    },
    load() {
      this.state = 'loading'
      teacherApi.getAttendanceSessions().then((d) => {
        this.sessions = (d && d.items) || []
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    createSession() {
      if (this.creating || !this.form.classId || !this.form.sessionDate) return
      this.creating = true
      teacherApi.createAttendanceSession({
        classId: Number(this.form.classId), courseName: this.form.courseName.trim() || undefined,
        termCode: this.form.termCode.trim() || undefined, sessionDate: this.form.sessionDate,
        slotNo: this.form.slotNo ? Number(this.form.slotNo) : undefined,
        sessionType: this.form.sessionType || undefined
      }).then(() => {
        uni.showToast({ title: '考勤场次已创建', icon: 'success' })
        this.showForm = false
        this.form = { classId: this.classOptions[0] ? this.classOptions[0].classId : '', courseName: '', termCode: '', sessionDate: '', slotNo: '', sessionType: '' }
        this.classIndex = 0
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '创建失败，请稍后重试'))
        .finally(() => { this.creating = false })
    },
    openSession(s) {
      this.active = s
      teacherApi.getAttendanceDetail(s.sessionId).then((d) => {
        this.active = d
        this.items = d.items || []
      }).catch(() => toast('加载失败'))
    },
    mark(it, status) {
      if (it.status === status) return
      const prev = it.status
      it.status = status
      teacherApi.markAttendance(this.active.sessionId, it.studentId, status).then((d) => {
        this.active.presentCount = d.presentCount
        this.active.absentCount = d.absentCount
      }).catch((e) => {
        it.status = prev
        toast(e && e.biz ? normalizeError(e).text : '标记失败，请稍后重试')
      })
    },
    submitSession() {
      if (this.submitting || !this.active) return
      this.submitting = true
      teacherApi.submitAttendanceSession(this.active.sessionId).then(() => {
        uni.showToast({ title: '考勤已提交', icon: 'success' })
        this.active = null
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.at__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.at__date { color: var(--text-primary); }
.at__ph { color: var(--text-tertiary); }
.at__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.at__back { display: inline-block; font-size: var(--font-size-sm); color: var(--brand-primary); margin-bottom: var(--space-3); }
.at__row { align-items: center; }
.at__seg { display: flex; flex-shrink: 0; border: 1px solid var(--border-base); border-radius: var(--radius-md); overflow: hidden; }
.at__seg-item { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 6px 8px; }
.at__seg-item.is-active { background: var(--brand-primary); color: #fff; }
</style>
