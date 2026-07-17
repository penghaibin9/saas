<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="教学任务确认" subtitle="确认 · 退回" show-back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!tasks.length" state="empty" title="暂无教学任务"
          description="分配给你的教学任务会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="t in tasks" :key="t.taskId" class="card at">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ t.courseName || '—' }}</text>
                <text class="at__sub">{{ t.courseCode || '' }} · {{ t.teachingClassName || t.teachingClassCode || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(t.status)" :type="statusTone(t.status)" />
            </view>
            <view class="at__row"><text class="at__row-k">学时</text><text class="flex-1 t-sm">周{{ t.weeklyHours || 0 }}节 · 共{{ t.totalHours || 0 }}节（第{{ t.startWeek || '-' }}~{{ t.endWeek || '-' }}周）</text></view>
            <view class="at__row" v-if="t.expectedStudents"><text class="at__row-k">人数</text><text class="flex-1 t-sm">{{ t.expectedStudents }} 人</text></view>
            <view class="at__row" v-if="t.status === 'REJECTED_BY_TEACHER' && t.rejectReason"><text class="at__row-k">退回原因</text><text class="flex-1 t-sm">{{ t.rejectReason }}</text></view>

            <view class="at__actions" v-if="t.status === 'ASSIGNED'">
              <button class="at__reject flex-1" :disabled="acting" @click="doReject(t)">退回</button>
              <button class="at__confirm flex-1" :disabled="acting" @click="doConfirm(t)">确认</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

const STATUS_LABELS = {
  ASSIGNED: '待确认', TEACHER_CONFIRMED: '已确认', REJECTED_BY_TEACHER: '已退回',
  READY: '已入库', MERGED: '已合班'
}
const STATUS_TONES = {
  ASSIGNED: 'warning', TEACHER_CONFIRMED: 'success', REJECTED_BY_TEACHER: 'danger',
  READY: 'success', MERGED: 'default'
}

export default {
  data() { return { tasks: [], state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    statusLabel(s) { return STATUS_LABELS[s] || s },
    statusTone(s) { return STATUS_TONES[s] || 'default' },
    load(done) {
      this.state = 'loading'
      teacherApi.getAcademicMyTasks().then((d) => {
        this.tasks = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    _err(e, label) {
      const code = e && String(e.code)
      if (code === 'APPROVAL_VERSION_CONFLICT') { toast((e && e.message) || '状态已变化，正在刷新'); this.load() }
      else if (code && code.startsWith('403')) toast((e && e.message) || '无权处理该任务')
      else toast((e && e.message) || label + '失败，请重试')
    },
    doConfirm(t) {
      if (this.acting) return
      uni.showModal({
        title: '确认教学任务', content: `确认承担「${t.courseName}」${t.teachingClassName || ''}的教学任务？`,
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.actAcademicTask(t.taskId, 'CONFIRM')
            .then(() => { toast('已确认'); this.load() })
            .catch((e) => this._err(e, '确认'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doReject(t) {
      if (this.acting) return
      uni.showModal({
        title: '退回教学任务', editable: true, placeholderText: '请填写退回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.actAcademicTask(t.taskId, 'REJECT', reason)
            .then(() => { toast('已退回'); this.load() })
            .catch((e) => this._err(e, '退回'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.at { display: flex; flex-direction: column; gap: var(--space-2); }
.at__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.at__row { display: flex; gap: var(--space-3); }
.at__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 56px; flex-shrink: 0; }
.at__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.at__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.at__reject::after { border: none; }
.at__confirm { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.at__confirm::after { border: none; }
</style>
