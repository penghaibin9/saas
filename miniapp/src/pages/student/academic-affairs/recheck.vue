<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="成绩复查申请" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的复查申请</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 发起复查' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="rc__group">选择要复查的成绩</text>
          <picker mode="selector" :range="gradeLabels" @change="onGradeChange">
            <view class="rc__input rc__picker">{{ picked >= 0 ? gradeLabels[picked] : '点击选择已发布成绩' }}</view>
          </picker>
          <textarea class="rc__textarea" v-model="reason" :maxlength="200"
                    placeholder="复查理由（必填，≥5字，如：核对卷面分/漏统计平时分）" placeholder-class="rc__ph" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting" @click="submit">
            {{ submitting ? '提交中…' : '提交复查申请' }}
          </button>
          <text class="rc__tip">仅可复查本人已发布成绩；同一门成绩在途复查仅限一条。</text>
        </view>

        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="r in d.items" :key="r.recheckId" class="list-row rc__item">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}<text v-if="r.term"> · {{ r.term }}</text></text>
              <text class="rc__sub">原 {{ r.originalScore }} 分<text v-if="r.status === 'ADJUSTED'"> → 调整为 {{ r.newScore }} 分</text></text>
              <text v-if="r.reviewNote" class="rc__note">复审意见：{{ r.reviewNote }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无复查申请" description="对已发布成绩有疑问，可点击右上角发起复查。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() {
    return { d: null, grades: [], state: 'loading', showForm: false, submitting: false, picked: -1, reason: '' }
  },
  computed: {
    gradeLabels() {
      return this.grades.map((g) => `${g.courseName}${g.term ? ' · ' + g.term : ''}（${g.score} 分）`)
    },
    canSubmit() {
      return this.picked >= 0 && this.reason.trim().length >= 5
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getMyRecheck(), studentApi.getMyTranscript()])
        .then(([mine, tr]) => {
          this.d = mine
          this.grades = (tr && tr.items ? tr.items : []).filter((g) => g.gradeId != null)
          this.state = 'ready'
        })
        .catch(() => { this.state = 'error' })
    },
    onGradeChange(e) { this.picked = Number(e.detail.value) },
    submit() {
      if (!this.canSubmit || this.submitting) return
      const g = this.grades[this.picked]
      if (!g) return
      this.submitting = true
      submitLock.run(() => studentApi.submitRecheck({ acadGradeId: g.gradeId, reason: this.reason.trim() }))
        .then(() => {
          uni.showToast({ title: '复查申请已提交', icon: 'success' })
          this.showForm = false
          this.picked = -1
          this.reason = ''
          this.load()
        }).catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试')
        }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.rc__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.rc__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.rc__picker { line-height: 40px; color: var(--text-primary); }
.rc__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.rc__ph { color: var(--text-tertiary); }
.rc__tip { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rc__item { align-items: flex-start; }
.rc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rc__note { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 4px; }
</style>
