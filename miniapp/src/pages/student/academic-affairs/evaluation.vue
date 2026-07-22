<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学生评教" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <text class="ev__hint">评教匿名提交，仅对本班开放窗口内课程打分。</text>
        <view class="list-group" v-if="d.list && d.list.length">
          <view v-for="t in d.list" :key="t.taskId" class="list-row ev__item">
            <view class="flex-1">
              <text class="t-md">{{ t.courseName || '课程' }}</text>
              <text class="ev__sub">{{ t.teacherName || '教师' }} · {{ t.batchName || '评教批次' }}</text>
              <text class="ev__sub">已提交 {{ t.submittedCount || 0 }} 份（班级合计）</text>
            </view>
            <button class="btn btn-primary btn-sm" :disabled="submitting === t.taskId" @click="openSubmit(t)">
              {{ submitting === t.taskId ? '提交中…' : '去评教' }}
            </button>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无开放评教" description="教务处开放评教窗口后，本班课程会出现在此。" />
      </view>
    </MobileGlobalState>

    <view v-if="active" class="ev__mask" @click="active = null">
      <view class="ev__sheet card stack-sm" @click.stop>
        <text class="ev__sheet-title">评价 · {{ active.courseName }}</text>
        <text class="ev__sub">授课教师 {{ active.teacherName || '—' }}（匿名）</text>
        <view class="ev__score-row">
          <text class="ev__label">综合分（0-100）</text>
          <input class="ev__input" type="number" v-model="score" placeholder="如 90" />
        </view>
        <textarea class="ev__textarea" v-model="comment" maxlength="200"
                  placeholder="选填：意见建议（匿名可见给教务统计）" />
        <button class="btn btn-primary" :disabled="!canSubmit || !!submitting" @click="submit">
          {{ submitting ? '提交中…' : '匿名提交' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() {
    return { d: null, state: 'loading', active: null, score: '90', comment: '', submitting: '' }
  },
  computed: {
    canSubmit() {
      const n = Number(this.score)
      return this.active && !Number.isNaN(n) && n >= 0 && n <= 100
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyEvaluationTasks().then((d) => {
        this.d = d || { list: [], total: 0 }
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    openSubmit(t) {
      this.active = t
      this.score = '90'
      this.comment = ''
    },
    submit() {
      if (!this.canSubmit || this.submitting) return
      const taskId = this.active.taskId
      this.submitting = taskId
      submitLock.run(() => studentApi.submitEvaluation({
        taskId,
        objectiveScore: Number(this.score),
        comment: (this.comment || '').trim() || undefined,
        answers: { overall: Number(this.score) },
      }))
        .then(() => {
          uni.showToast({ title: '已匿名提交', icon: 'success' })
          this.active = null
          this.load()
        })
        .catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '提交失败')
        })
        .finally(() => { this.submitting = '' })
    }
  }
}
</script>

<style scoped>
.ev__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.ev__item { align-items: center; gap: var(--space-2); }
.ev__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ev__mask { position: fixed; inset: 0; background: rgba(15,23,42,0.45); display: flex; align-items: flex-end; z-index: 40; }
.ev__sheet { width: 100%; border-radius: var(--radius-lg) var(--radius-lg) 0 0; padding: var(--space-4); }
.ev__sheet-title { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.ev__score-row { display: flex; align-items: center; gap: var(--space-2); }
.ev__label { font-size: var(--font-size-sm); color: var(--text-secondary); white-space: nowrap; }
.ev__input { flex: 1; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 8px 10px; }
.ev__textarea { width: 100%; min-height: 80px; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 8px 10px; box-sizing: border-box; }
.btn-sm { padding: 4px 10px; font-size: var(--font-size-xs); }
</style>
