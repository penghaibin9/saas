<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调停课审批" subtitle="待我审批" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批调停课"
          description="轮到你审批的调课/停课/补课会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="x.changeId" class="card ed" :class="{ 'is-target': isTarget(x) }">
            <text v-if="isTarget(x)" class="ed__target">从工作台直达的申请</text>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.courseName || '—' }}</text>
                <text class="ed__sub">{{ x.changeTypeLabel || x.changeType }} · {{ x.teacherName || x.teacherKey || '' }}</text>
              </view>
              <MobileStatusTag :label="x.status" type="warning" />
            </view>
            <view class="ed__row" v-if="x.reason"><text class="ed__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="ed__actions">
              <button class="ed__reject flex-1" :disabled="acting" @click="doAct(x, 'REJECT')">驳回</button>
              <button class="ed__approve flex-1" :disabled="acting" @click="doAct(x, 'APPROVE')">通过</button>
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
  data() { return { list: [], state: 'loading', acting: false, targetChangeId: '' } },
  onLoad(options = {}) {
    this.targetChangeId = String(options.id || options.changeId || '')
    this.load()
  },
  methods: {
    isTarget(item) { return !!this.targetChangeId && String(item.changeId || item.scheduleChangeId || '') === this.targetChangeId },
    focusTarget(rows) {
      if (!this.targetChangeId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该调停课申请不存在、已处理或不在当前审批范围内')
        this.targetChangeId = ''
        return rows
      }
      if (index === 0) return rows
      return [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    load() {
      this.state = 'loading'
      teacherApi.getScheduleChangePending().then((d) => {
        this.list = this.focusTarget((d && (d.list || d.items)) || [])
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    doAct(x, action) {
      if (this.acting) return
      const need = action === 'REJECT'
      uni.showModal({
        title: action === 'APPROVE' ? '通过调停课' : '驳回调停课',
        editable: need, placeholderText: need ? '驳回原因（≥5字）' : '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (need && comment.length < 5) { toast('原因至少 5 字'); return }
          this.acting = true
          teacherApi.reviewScheduleChange(x.changeId, action, comment)
            .then(() => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.targetChangeId = ''; this.load() })
            .catch((e) => {
              const code = String((e && e.code) || '')
              if (code.startsWith('409') || code === 'APPROVAL_VERSION_CONFLICT') {
                toast((e && e.message) || '该申请已处理，正在刷新')
                this.targetChangeId = ''
                this.load()
              } else if (code.startsWith('403')) toast((e && e.message) || '当前身份无权审批')
              else toast((e && e.message) || '审批失败')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>
<style scoped>
.ed { display: flex; flex-direction: column; gap: var(--space-2); }
.ed.is-target { border: 1px solid var(--teacher-500); box-shadow: 0 0 0 2px var(--teacher-50); }
.ed__target { color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.ed__sub { display:block; color: var(--text-tertiary); font-size: var(--font-size-xs); margin-top: 4px; }
.ed__row { display:flex; gap: var(--space-2); margin-top: 6px; }
.ed__row-k { color: var(--text-tertiary); font-size: var(--font-size-xs); width: 48px; }
.ed__actions { display:flex; gap: var(--space-2); margin-top: 10px; }
.ed__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ed__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ed__reject::after, .ed__approve::after { border: none; }
</style>
