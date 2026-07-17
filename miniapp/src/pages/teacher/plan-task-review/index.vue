<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习计划任务确认" subtitle="学生提交的计划任务完成情况" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待确认任务"
          description="本人指导学生提交实习计划任务完成情况后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="p in list" :key="p.id" class="card pt">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ p.studentName || '—' }}</text>
                <text class="pt__sub">{{ p.studentNo || '' }} · 任务{{ p.taskSortOrder }} · {{ p.taskName }}</text>
              </view>
              <MobileStatusTag :label="p.statusLabel" type="warning" />
            </view>
            <view class="pt__note" v-if="p.studentNote"><text class="flex-1 t-sm">{{ p.studentNote }}</text></view>
            <text class="pt__file" v-if="p.evidenceFileId">已上传完成凭证</text>
            <text class="pt__time" v-if="p.submittedAt">提交于 {{ p.submittedAt.slice(0, 16).replace('T', ' ') }}</text>
            <view class="pt__actions">
              <button class="pt__reject flex-1" :disabled="acting" @click="review(p, 'REJECT')">退回</button>
              <button class="pt__approve flex-1" :disabled="acting" @click="review(p, 'APPROVE')">确认完成</button>
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

export default {
  data() { return { list: null, state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getPlanTaskPending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    review(p, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '退回任务' : '确认完成',
        editable: true, placeholderText: reject ? '请填写退回原因（≥5 字）' : '可填写确认意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewPlanTask(p.id, action, comment)
            .then(() => { toast(reject ? '已退回' : '已确认完成'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast('该任务已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '退回' : '确认') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.pt { display: flex; flex-direction: column; gap: var(--space-2); }
.pt__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.pt__note { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.pt__file { font-size: var(--font-size-xs); color: var(--success-600); }
.pt__time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.pt__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.pt__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.pt__reject::after { border: none; }
.pt__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.pt__approve::after { border: none; }
</style>
