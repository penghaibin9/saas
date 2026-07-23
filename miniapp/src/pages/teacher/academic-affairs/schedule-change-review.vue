<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调停课审批" subtitle="待我审批" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批调停课"
          description="轮到你审批的调课/停课/补课会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="x.changeId" class="card ed">
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
  data() { return { list: [], state: 'loading', acting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getScheduleChangePending().then((d) => {
        this.list = (d && d.list) || []; this.state = 'ready'
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
            .then(() => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.load() })
            .catch((e) => toast((e && e.message) || '审批失败'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>
<style scoped>
.ed__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.ed__row { display:flex; gap: 8px; margin-top: 6px; }
.ed__row-k { color: var(--t3); font-size: 12px; width: 48px; }
.ed__actions { display:flex; gap: 8px; margin-top: 10px; }
.ed__reject, .ed__approve { font-size: 13px; }
</style>
