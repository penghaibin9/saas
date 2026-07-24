<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的考勤" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="t-sm">出勤 {{ d.summary.PRESENT || 0 }} · 迟到 {{ d.summary.LATE || 0 }} · 旷课 {{ d.summary.ABSENT || 0 }} · 请假 {{ d.summary.LEAVE || 0 }}</text>
          <text class="mk__sub">{{ d.note }}</text>
        </view>
        <MobileGlobalState v-if="!d.items.length" state="empty" title="暂无考勤记录" :description="d.note" />
        <view v-for="it in d.items" :key="it.sessionId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName || '课堂点名' }}</text>
            <text class="mk__sub">{{ it.sessionDate }} · 第{{ it.slotNo || '—' }}节 · {{ it.sessionType }}</text>
          </view>
          <MobileStatusTag :status="it.status" />
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { studentApi } from '@/services/studentApi'
export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyAttendance().then((d) => { this.d = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>
<style scoped>
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
