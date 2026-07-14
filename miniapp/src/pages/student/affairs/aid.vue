<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="困难认定" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card" v-if="d.currentLevel">
          <text class="aid__label">当前认定等级</text>
          <text class="aid__level">{{ d.currentLevel }}</text>
        </view>

        <view class="section-head"><text class="section-head__title">申请记录</text></view>
        <view class="list-group" v-if="d.items.length">
          <view v-for="x in d.items" :key="x.applyId" class="list-row">
            <view class="flex-1">
              <text class="t-md">申请等级：{{ x.applyLevel || '—' }}</text>
              <text class="aid__sub" v-if="x.finalLevel">认定等级：{{ x.finalLevel }}</text>
            </view>
            <MobileStatusTag :status="x.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="如需申请请联系辅导员。" />
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
      studentApi.getMyAid().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.aid__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.aid__level { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px; }
.aid__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
