<template>
  <view class="page-wrap">
    <MobileNavBar title="岗前安全教育" subtitle="当前所选批次全部必修课程" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready'">
        <MobileInlineAlert type="info" :description="batchId ? '上岗前须完成所选批次全部必修课程；旧版本课程通过记录不能代替新版本。' : '当前只有一条进行中实习记录，系统已使用该批次。'" />
        <MobileGlobalState v-if="!courses.length" state="empty" title="暂无安全教育课程"
          description="如学校已要求安全教育但此处无课程，请联系指导教师或学校管理员。" />
        <view v-for="course in courses" :key="course.id" class="card ss" @click="open(course)">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ course.title }}</text>
              <text class="ss__sub">版本 {{ course.courseVersion }} · 要求学习 {{ course.requiredMinutes }} 分钟</text>
            </view>
            <MobileStatusTag :label="statusLabel(course.completionStatus)" :type="statusTone(course.completionStatus)" />
          </view>
          <view class="ss__progress">
            <text>已学习 {{ course.studiedMinutes || 0 }} 分钟</text>
            <text>剩余尝试 {{ course.remainingAttempts }}</text>
          </view>
          <text v-if="course.requireCommitment" class="ss__commit">安全承诺：{{ course.commitmentConfirmed ? '已确认' : '待确认' }}</text>
          <text class="ss__action">{{ actionLabel(course) }} ›</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

export default {
  data() { return { state: 'loading', courses: [], batchId: '' } },
  onLoad(options) {
    this.batchId = String(options?.batchId || '')
    this.load()
  },
  onShow() { if (this.state === 'ready') this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.state = 'loading'
      try {
        const [courses, completions] = await Promise.all([
          studentApi.getInternshipSafetyCourses(this.batchId),
          studentApi.getInternshipSafetyCompletions(this.batchId)
        ])
        const completionRows = Array.isArray(completions) ? completions : (completions?.items || [])
        const cmap = Object.fromEntries(completionRows.map((x) => [String(x.courseId), x]))
        this.courses = (Array.isArray(courses) ? courses : (courses?.items || [])).map((x) => ({
          ...x,
          ...(cmap[String(x.id)] || {}),
          id: x.id,
          courseVersion: x.courseVersion,
          completionStatus: x.completionStatus || (cmap[String(x.id)] || {}).status || 'NOT_STARTED',
          commitmentConfirmed: !!(cmap[String(x.id)] || {}).commitmentConfirmed
        }))
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      } finally { done && done() }
    },
    open(course) {
      const query = [`id=${encodeURIComponent(course.id)}`]
      if (this.batchId) query.push(`batchId=${encodeURIComponent(this.batchId)}`)
      go(`/pages/student/internship/safety/course?${query.join('&')}`)
    },
    statusLabel(status) {
      return ({ NOT_STARTED: '未开始', IN_PROGRESS: '学习中', PENDING_REVIEW: '待审核',
        PASSED: '已通过', FAILED: '未通过' })[status] || status || '未开始'
    },
    statusTone(status) {
      if (status === 'PASSED') return 'success'
      if (status === 'FAILED') return 'danger'
      return 'warning'
    },
    actionLabel(course) {
      if (course.completionStatus === 'PASSED') return '查看完成记录'
      if (course.completionStatus === 'PENDING_REVIEW') return '查看审核状态'
      if (course.completionStatus === 'FAILED') return '重新学习'
      if (course.completionStatus === 'IN_PROGRESS') return '继续学习'
      return '开始学习'
    }
  }
}
</script>

<style scoped>
.ss { display: flex; flex-direction: column; gap: var(--space-2); }
.ss__sub { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ss__progress { display: flex; justify-content: space-between; font-size: var(--font-size-xs); color: var(--text-secondary); }
.ss__commit { font-size: var(--font-size-xs); color: var(--warning-700); }
.ss__action { align-self: flex-end; color: var(--brand-primary); font-size: var(--font-size-sm); }
</style>
