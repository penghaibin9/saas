<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的请假" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <view class="lv__empty" v-if="!items.length"><text>暂无请假记录</text></view>
        <view class="stack">
          <view v-for="x in items" :key="x.leaveId" class="lv__card">
            <view class="lv__row">
              <text class="lv__type">{{ typeText(x.leaveType) }}</text>
              <text class="lv__badge" :class="badgeClass(x.status)">{{ statusText(x.status) }}</text>
            </view>
            <text class="lv__time">{{ (x.startTime || '').slice(0, 10) }} 至 {{ (x.endTime || '').slice(0, 10) }} · {{ x.days }} 天</text>
            <text class="lv__reason" v-if="x.reason">{{ x.reason }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
const TYPE = { SICK: '病假', PERSONAL: '事假', GOOUT: '外出' }
const STATUS = { COUNSELOR_REVIEW: '辅导员审批', COLLEGE_REVIEW: '学院审批', STUDENT_AFFAIRS_REVIEW: '学工处审批',
  APPROVED: '已通过', REJECTED: '已驳回', RETURNED: '已退回', WAIT_CANCEL_LEAVE: '待销假', CLOSED: '已销假',
  OVERDUE: '已逾期', EXTENSION_REVIEW: '续假审批中' }
export default {
  data() { return { items: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyLeaves().then((d) => { this.items = d.items || []; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    typeText(t) { return TYPE[t] || t },
    statusText(s) { return STATUS[s] || s },
    badgeClass(s) {
      if (['APPROVED', 'CLOSED'].includes(s)) return 'is-ok'
      if (['REJECTED', 'OVERDUE'].includes(s)) return 'is-bad'
      return 'is-wait'
    }
  }
}
</script>

<style scoped>
.lv__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.lv__card { background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.lv__row { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2); }
.lv__type { font-weight: 600; }
.lv__badge { font-size: var(--font-size-xs); padding: 2px 10px; border-radius: var(--radius-full); }
.lv__badge.is-ok { background: rgba(34,197,94,0.12); color: #16a34a; }
.lv__badge.is-bad { background: rgba(239,68,68,0.12); color: #dc2626; }
.lv__badge.is-wait { background: rgba(234,179,8,0.14); color: #b45309; }
.lv__time { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lv__reason { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 4px; }
</style>
