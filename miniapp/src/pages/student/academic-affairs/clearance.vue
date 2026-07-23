<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="清考结果" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card"><text class="mk__sub">{{ d.note }}</text></view>
        <MobileGlobalState v-if="!d.items.length" state="empty" title="暂无清考安排" :description="d.note" />
        <view v-for="it in d.items" :key="it.recordId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName }}</text>
            <text class="mk__sub">{{ it.batchName || '清考批次' }} · 原分 {{ it.originScore ?? '—' }} · 清考分 {{ it.score ?? '—' }}</text>
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
      studentApi.getMyClearance().then((d) => { this.d = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>
<style scoped>
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
