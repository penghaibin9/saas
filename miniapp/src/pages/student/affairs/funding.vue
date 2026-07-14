<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="奖助申请" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="list-group" v-if="d.items.length">
          <view v-for="x in d.items" :key="x.applicationId" class="list-row">
            <text class="flex-1 t-md">{{ x.projectType || '—' }}</text>
            <MobileStatusTag :status="x.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无奖助申请记录" description="如需申请请联系辅导员或关注学院通知。" />
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
      studentApi.getMyFunding().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>
