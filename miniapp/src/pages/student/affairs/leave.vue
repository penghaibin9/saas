<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的请假" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无请假记录" description="发起请假后记录会显示在这里。" />
        <view class="list-group" v-else>
          <view v-for="x in items" :key="x.leaveId" class="list-row lv__row">
            <view class="flex-1">
              <text class="t-md">{{ typeText(x.leaveType) }}</text>
              <text class="lv__time">{{ (x.startTime || '').slice(0, 10) }} 至 {{ (x.endTime || '').slice(0, 10) }} · {{ x.days }} 天</text>
              <text class="lv__reason" v-if="x.reason">{{ x.reason }}</text>
            </view>
            <MobileStatusTag :label="statusText(x.status)" :type="badgeType(x.status)" />
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
    badgeType(s) {
      if (['APPROVED', 'CLOSED'].includes(s)) return 'success'
      if (['REJECTED', 'OVERDUE'].includes(s)) return 'danger'
      return 'warning'
    }
  }
}
</script>

<style scoped>
.lv__row { align-items: flex-start; }
.lv__time { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.lv__reason { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
</style>
