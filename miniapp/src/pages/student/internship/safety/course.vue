<template>
  <view class="page-wrap">
    <MobileNavBar title="安全教育课程" subtitle="服务端计时 · 教师审核" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready' && course">
        <view class="card sc__head">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-lg t-bold">{{ course.title }}</text>
              <text class="sc__sub">课程版本 {{ course.courseVersion }} · 通过分 {{ course.passingScore }}</text>
            </view>
            <MobileStatusTag :label="statusLabel" :type="statusTone" />
          </view>
          <view class="sc__metrics">
            <view><text class="sc__metric-val">{{ trustedMinutes }}</text><text class="sc__metric-label">已学习分钟</text></view>
            <view><text class="sc__metric-val">{{ course.requiredMinutes }}</text><text class="sc__metric-label">要求分钟</text></view>
            <view><text class="sc__metric-val">{{ course.remainingAttempts }}</text><text class="sc__metric-label">剩余尝试</text></view>
          </view>
        </view>

        <view class="card sc__body">
          <text class="sc__body-title">课程正文</text>
          <text class="sc__content" selectable>{{ course.contentSnapshot || '课程正文为空，请联系学校管理员。' }}</text>
        </view>

        <view v-if="course.requireCommitment" class="card sc__commit">
          <view class="row-between">
            <text class="t-md t-bold">安全承诺</text>
            <MobileStatusTag :label="commitmentConfirmed ? '已确认' : '待确认'" :type="commitmentConfirmed ? 'success' : 'warning'" />
          </view>
          <text class="sc__commit-text">本人已阅读本课程，承诺遵守岗位安全操作规程，发现风险立即停止作业并向企业导师、校内指导教师报告。</text>
          <button v-if="completion && !commitmentConfirmed" class="btn btn-ghost" :disabled="submitting" @click="commitment">确认安全承诺</button>
        </view>

        <MobileInlineAlert v-if="completionStatus === 'PENDING_REVIEW'" type="info" description="学习结果已提交，等待指导教师审核。审核完成后会在此显示结果。" />
        <MobileInlineAlert v-if="completionStatus === 'FAILED'" type="warning" description="本次审核未通过，可在剩余次数内重新学习并提交。" />
        <MobileInlineAlert v-if="completionStatus === 'PASSED'" type="success" description="本课程已通过。只有当前批次全部必修课程通过后，上岗安全教育才算完成。" />
        <MobileInlineAlert v-if="completion && trustedMinutes < Number(course.requiredMinutes || 0)" type="warning"
          :description="`服务端可信学习时长尚差 ${Number(course.requiredMinutes || 0) - trustedMinutes} 分钟；停留页面不会绕过服务端计时。`" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && course && completionStatus !== 'PASSED' && completionStatus !== 'PENDING_REVIEW'">
      <button v-if="!completion" class="btn btn-primary flex-1" :disabled="submitting" @click="start">开始学习</button>
      <button v-else class="btn btn-primary flex-1" :disabled="!canSubmit || submitting" @click="submit">
        {{ submitting ? '提交中…' : (canSubmit ? '提交学习结果' : '完成学习时长后提交') }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { id: '', course: null, state: 'loading', submitting: false, now: Date.now(), timer: null }
  },
  computed: {
    completion() { return this.course?.completion || null },
    completionStatus() { return this.completion?.status || this.course?.completionStatus || 'NOT_STARTED' },
    commitmentConfirmed() { return !!this.completion?.commitmentConfirmed },
    trustedMinutes() {
      const stored = Number(this.completion?.studiedMinutes || this.course?.studiedMinutes || 0)
      if (!this.completion?.startedAt) return stored
      const start = new Date(this.completion.startedAt).getTime()
      if (!Number.isFinite(start)) return stored
      return Math.max(stored, Math.floor((this.now - start) / 60000))
    },
    canSubmit() {
      if (!this.completion) return false
      if (this.course.requireCommitment && !this.commitmentConfirmed) return false
      if (this.completionStatus === 'PASSED' || this.completionStatus === 'PENDING_REVIEW') return false
      return this.trustedMinutes >= Number(this.course.requiredMinutes || 0)
    },
    statusLabel() {
      return ({ NOT_STARTED: '未开始', IN_PROGRESS: '学习中', PENDING_REVIEW: '待审核',
        PASSED: '已通过', FAILED: '未通过' })[this.completionStatus] || this.completionStatus
    },
    statusTone() {
      if (this.completionStatus === 'PASSED') return 'success'
      if (this.completionStatus === 'FAILED') return 'danger'
      return 'warning'
    }
  },
  onLoad(options) {
    this.id = options?.id || ''
    this.timer = setInterval(() => { this.now = Date.now() }, 15000)
    this.load()
  },
  onUnload() { if (this.timer) clearInterval(this.timer) },
  methods: {
    async load() {
      if (!this.id) { this.state = 'error'; return }
      this.state = 'loading'
      try {
        this.course = await studentApi.getInternshipSafetyCourseDetail(this.id)
        this.now = Date.now()
        this.state = 'ready'
      } catch (e) { this.state = 'error' }
    },
    async start() {
      if (this.submitting) return
      this.submitting = true
      try {
        await studentApi.startInternshipSafetyCourse(this.id)
        toast('课程学习已开始')
        await this.load()
      } catch (e) { toast(normalizeError(e).text || '开始失败，请重试') }
      finally { this.submitting = false }
    },
    deviceDigest() {
      try {
        const s = uni.getSystemInfoSync()
        return [s.platform, s.model, s.system, s.appVersion].filter(Boolean).join('|')
      } catch (e) { return 'miniapp-device' }
    },
    commitment() {
      if (!this.completion || this.submitting) return
      uni.showModal({
        title: '确认安全承诺',
        content: '确认本人已阅读课程正文，并承诺遵守岗位安全规程？',
        success: async (r) => {
          if (!r.confirm) return
          this.submitting = true
          try {
            await studentApi.commitInternshipSafety(this.completion.id, {
              expectedVersion: this.completion.version,
              contentHash: this.course.contentHash,
              deviceDigest: this.deviceDigest()
            })
            toast('安全承诺已确认')
            await this.load()
          } catch (e) {
            toast(normalizeError(e).text || '确认失败，请刷新后重试')
            if (String(e?.code || '').includes('CONFLICT')) await this.load()
          } finally { this.submitting = false }
        }
      })
    },
    async submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      try {
        await studentApi.submitInternshipSafetyCourse(this.id, {
          expectedVersion: this.completion.version,
          studiedMinutes: this.trustedMinutes,
          answers: { readAndUnderstood: true }
        })
        toast('学习结果已提交审核')
        await this.load()
      } catch (e) {
        toast(normalizeError(e).text || '提交失败，请重试')
        if (String(e?.code || '').includes('CONFLICT')) await this.load()
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.sc__head, .sc__body, .sc__commit { display: flex; flex-direction: column; gap: var(--space-3); }
.sc__sub { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sc__metrics { display: flex; justify-content: space-around; text-align: center; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-3); }
.sc__metric-val { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--brand-primary); }
.sc__metric-label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.sc__body-title { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.sc__content { white-space: pre-wrap; line-height: 1.8; color: var(--text-secondary); }
.sc__commit-text { font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.7; }
</style>
