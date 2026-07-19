<template>
  <view class="page-wrap pl">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="plan">
        <view class="card">
          <text class="card-title">{{ plan.title }}</text>
          <text class="pl__status">{{ plan.ackStatusLabel }}</text>
          <view v-if="summary.total" class="pl__prog">
            <text>任务完成 {{ summary.approved }}/{{ summary.total }}（{{ summary.rate }}%）</text>
            <view class="pl__bar"><view class="pl__bar-in" :style="{ width: summary.rate + '%' }" /></view>
          </view>
        </view>
        <view class="card">
          <text class="pl__label">实习目标</text>
          <text class="pl__text">{{ plan.objectives || '—' }}</text>
          <text class="pl__label">计划正文</text>
          <text class="pl__text">{{ plan.content }}</text>
        </view>
        <view v-if="tasks.length" class="card">
          <text class="pl__label">实习任务清单</text>
          <view v-for="(t, i) in tasks" :key="i" class="pl__task">
            <view class="pl__task-head">
              <text class="pl__task-no">{{ t.sortOrder || i + 1 }}</text>
              <text class="pl__task-name">{{ t.name || t.taskName }}</text>
              <text class="pl__task-st">{{ t.progressStatusLabel || t.statusLabel || '未开始' }}</text>
            </view>
            <text v-if="t.requirement" class="pl__task-req">{{ t.requirement }}</text>
            <text v-if="t.deadline" class="pl__task-dl">截止：{{ formatDeadline(t.deadline) }}</text>
            <text v-if="t.reviewComment" class="pl__task-reject">退回：{{ t.reviewComment }}</text>
            <view v-if="canSubmit(t)" class="pl__task-act">
              <textarea v-model="t._note" class="pl__input" placeholder="填写完成说明（至少5字）" />
              <button class="btn btn-secondary btn-sm" :disabled="submitting === t.sortOrder" @click="submitTask(t)">
                提交完成
              </button>
            </view>
          </view>
        </view>
      </view>
      <view v-else class="page-pad"><MobileGlobalState state="empty" title="暂无实习计划" description="待学院发布批次实习计划书" /></view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="plan && plan.ackStatus === 'PENDING'">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="ack">确认已阅读计划</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, back } from '@/utils/nav'
export default {
  data() { return { pageState: 'loading', plan: null, tasks: [], summary: { total: 0, approved: 0, rate: 0 }, submitting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.pageState = 'loading'
      Promise.all([
        studentApi.getInternshipPlan(),
        studentApi.getInternshipPlanTasks().catch(() => null)
      ]).then(([plan, taskData]) => {
        this.plan = plan
        if (taskData && taskData.tasks) {
          this.tasks = taskData.tasks.map((t) => ({ ...t, _note: '' }))
          this.summary = taskData.summary || this.summary
        } else if (plan && plan.tasks) {
          this.tasks = plan.tasks.map((t) => ({ ...t, _note: '' }))
          this.summary = plan.taskSummary || this.summary
        } else {
          this.tasks = []
        }
        this.pageState = plan ? 'ready' : 'empty'
      }).catch(() => { this.pageState = 'error' })
    },
    canSubmit(t) {
      if (!this.plan || this.plan.ackStatus !== 'ACKNOWLEDGED') return false
      const st = t.progressStatus || t.status
      return st === 'NOT_STARTED' || st === 'REJECTED'
    },
    ack() {
      if (this.submitting !== false) return
      this.submitting = true
      studentApi.ackInternshipPlan().then(() => {
        toast('已确认实习计划')
        this.load()
      }).catch((e) => toast((e && e.message) || '确认失败')).finally(() => { this.submitting = false })
    },
    submitTask(t) {
      if (this.submitting !== false) return
      const note = (t._note || '').trim()
      if (note.length < 5) return toast('完成说明至少5字')
      this.submitting = t.sortOrder
      studentApi.submitInternshipPlanTask(t.sortOrder, { studentNote: note }).then(() => {
        toast('已提交，待教师确认')
        this.load()
      }).catch((e) => toast((e && e.message) || '提交失败')).finally(() => { this.submitting = false })
    },
    formatDeadline(v) {
      if (!v) return '—'
      const s = String(v).replace('T', ' ').slice(0, 16)
      return s.endsWith('23:59') ? s.slice(0, 10) + ' 23:59' : s
    }
  }
}
</script>

<style scoped>
.pl__status { display: block; margin-top: 6px; font-size: var(--font-size-sm); color: var(--warning-600); }
.pl__prog { margin-top: 10px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pl__bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin-top: 6px; overflow: hidden; }
.pl__bar-in { height: 100%; background: var(--primary-500, #2563eb); border-radius: 3px; }
.pl__label { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); margin: 10px 0 4px; }
.pl__text { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.6; white-space: pre-wrap; }
.pl__task { margin-top: 10px; padding: 10px; background: var(--bg-subtle, #f8fafc); border-radius: 8px; }
.pl__task-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pl__task-no { width: 22px; height: 22px; line-height: 22px; text-align: center; border-radius: 50%; background: var(--primary-100, #dbeafe); color: var(--primary-700, #1d4ed8); font-size: 12px; font-weight: 600; }
.pl__task-name { flex: 1; font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.pl__task-st { font-size: 11px; color: var(--warning-700, #b45309); }
.pl__task-req { display: block; margin-top: 6px; font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.5; }
.pl__task-dl { display: block; margin-top: 4px; font-size: var(--font-size-xs); color: var(--warning-700, #b45309); }
.pl__task-reject { display: block; margin-top: 4px; font-size: var(--font-size-xs); color: var(--danger-600, #dc2626); }
.pl__task-act { margin-top: 8px; }
.pl__input { width: 100%; min-height: 64px; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; margin-bottom: 6px; box-sizing: border-box; }
</style>
