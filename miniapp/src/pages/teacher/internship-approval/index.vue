<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习审批" subtitle="本人指导学生的补卡与请假申请" show-back />

    <view class="ia__tabs">
      <view class="ia__tab" :class="{ 'is-on': tab === 'makeup' }" @click="switchTab('makeup')">
        补卡审批<text v-if="makeups && makeups.length" class="ia__tab-badge">{{ makeups.length }}</text>
        <text v-if="tab === 'makeup'" class="ia__tab-u" />
      </view>
      <view class="ia__tab" :class="{ 'is-on': tab === 'leave' }" @click="switchTab('leave')">
        请假审批<text v-if="leaves && leaves.length" class="ia__tab-badge">{{ leaves.length }}</text>
        <text v-if="tab === 'leave'" class="ia__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 补卡审批 -->
      <view class="page-pad" v-if="tab === 'makeup'">
        <MobileGlobalState v-if="!makeups || !makeups.length" state="empty" title="暂无待审补卡"
          description="本人指导学生的补卡申请会出现在这里，通过后自动补写打卡记录。" />
        <view class="stack" v-else>
          <view v-for="m in makeups" :key="m.id" class="card ia">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ m.studentName || '—' }}</text>
                <text class="ia__sub">{{ m.studentNo || '' }} · {{ m.makeupTypeLabel || m.makeupType }}</text>
              </view>
              <MobileStatusTag :label="m.statusLabel || '待审核'" type="warning" />
            </view>
            <view class="ia__row"><text class="ia__row-k">补卡日期</text><text class="flex-1 t-sm">{{ m.checkinDate || '—' }}</text></view>
            <view class="ia__row"><text class="ia__row-k">事由</text><text class="flex-1 t-sm">{{ m.reason || '—' }}</text></view>
            <view class="ia__actions">
              <button class="ia__reject flex-1" @click="review('makeup', m, 'REJECT')">驳回</button>
              <button class="ia__approve flex-1" @click="review('makeup', m, 'APPROVE')">通过</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 请假审批 -->
      <view class="page-pad" v-if="tab === 'leave'">
        <MobileGlobalState v-if="!leaves || !leaves.length" state="empty" title="暂无待审请假"
          description="本人指导学生的实习请假申请会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="l in leaves" :key="l.id" class="card ia">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ l.studentName || '—' }}</text>
                <text class="ia__sub">{{ l.studentNo || '' }} · {{ l.leaveTypeLabel || l.leaveType }} · {{ l.days || 0 }} 天</text>
              </view>
              <MobileStatusTag :label="l.statusLabel || '待审批'" type="warning" />
            </view>
            <view class="ia__row"><text class="ia__row-k">起止</text><text class="flex-1 t-sm">{{ l.startDate || '—' }} ~ {{ l.endDate || '—' }}</text></view>
            <view class="ia__row"><text class="ia__row-k">事由</text><text class="flex-1 t-sm">{{ l.reason || '—' }}</text></view>
            <view class="ia__actions">
              <button class="ia__reject flex-1" @click="review('leave', l, 'REJECT')">驳回</button>
              <button class="ia__approve flex-1" @click="review('leave', l, 'APPROVE')">通过</button>
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
  data() { return { tab: 'makeup', makeups: null, leaves: null, state: 'loading', acting: false } },
  onLoad(options) {
    if (options && options.tab === 'leave') this.tab = 'leave'
    this.load()
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    switchTab(t) { if (this.tab !== t) { this.tab = t; if ((t === 'makeup' && !this.makeups) || (t === 'leave' && !this.leaves)) this.load() } },
    load(done) {
      this.state = 'loading'
      Promise.all([
        teacherApi.getMakeupPending().catch(() => ({ list: [] })),
        teacherApi.getLeavePending().catch(() => ({ list: [] }))
      ]).then(([mk, lv]) => {
        this.makeups = (mk && mk.list) || []
        this.leaves = (lv && lv.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    review(kind, item, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      const title = kind === 'makeup' ? '补卡' : '请假'
      uni.showModal({
        title: (reject ? '驳回' : '通过') + title,
        editable: true,
        placeholderText: reject ? `请填写驳回原因（≥5 字）` : '可填写审批意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          const fn = kind === 'makeup' ? teacherApi.reviewMakeup : teacherApi.reviewLeave
          fn(item.id, action, comment)
            .then(() => { toast(reject ? '已驳回' : '已通过'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code && (code.startsWith('409') || code === 'DATA_CONFLICT')) { toast('该申请已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的指导范围内')
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
.ia__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ia__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ia__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ia__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ia__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ia { display: flex; flex-direction: column; gap: var(--space-2); }
.ia__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ia__row { display: flex; gap: var(--space-3); }
.ia__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 60px; flex-shrink: 0; }
.ia__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ia__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ia__reject::after { border: none; }
.ia__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ia__approve::after { border: none; }
</style>
