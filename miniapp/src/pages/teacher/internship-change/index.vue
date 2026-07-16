<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调岗退岗初审" subtitle="本人指导学生的换岗/换单位/自主实习变更" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审变更"
          description="本人指导学生发起换岗/换单位/自主实习变更申请后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="c in list" :key="c.id" class="card ic">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ c.studentName || '—' }}</text>
                <text class="ic__sub">{{ c.studentNo || '' }} · {{ c.changeTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="c.statusLabel" type="warning" />
            </view>
            <view class="ic__compare">
              <view class="ic__compare-row"><text class="ic__compare-k">现单位/岗位</text><text class="flex-1 t-sm">{{ c.currentEnterprise || '—' }} · {{ c.currentPosition || '—' }}</text></view>
              <view class="ic__compare-arrow">↓</view>
              <view class="ic__compare-row"><text class="ic__compare-k">拟变更为</text><text class="flex-1 t-sm">{{ c.targetEnterpriseName || c.currentEnterprise || '—' }} · {{ c.targetPositionName || '—' }}</text></view>
            </view>
            <view class="ic__row"><text class="ic__row-k">理由</text><text class="flex-1 t-sm">{{ c.reason || '—' }}</text></view>
            <view class="ic__actions">
              <button class="ic__reject flex-1" :disabled="acting" @click="review(c, 'REJECT')">驳回</button>
              <button class="ic__approve flex-1" :disabled="acting" @click="review(c, 'APPROVE')">通过</button>
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
      teacherApi.getInternshipChangePending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    review(c, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回变更' : '通过变更',
        editable: true, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewInternshipChange(c.id, action, comment)
            .then(() => { toast(reject ? '已驳回' : '已通过'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast('该申请已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '驳回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ic { display: flex; flex-direction: column; gap: var(--space-2); }
.ic__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ic__compare { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ic__compare-row { display: flex; gap: var(--space-3); padding: 3px 0; }
.ic__compare-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.ic__compare-arrow { text-align: center; color: var(--teacher-500); font-size: var(--font-size-sm); }
.ic__row { display: flex; gap: var(--space-3); }
.ic__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }
.ic__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ic__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ic__reject::after { border: none; }
.ic__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ic__approve::after { border: none; }
</style>
