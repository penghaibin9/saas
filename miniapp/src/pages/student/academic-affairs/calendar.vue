<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="校历" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card" v-if="d.hasTerm">
          <text class="t-md t-bold">当前学期 {{ d.termLabel }}</text>
          <text class="mk__sub" v-if="d.note">{{ d.note }}</text>
        </view>
        <MobileGlobalState v-else state="empty" :title="d.note || '尚未设置当前学期'" />
        <view class="section-head"><text class="section-head__title">校历事件</text></view>
        <MobileGlobalState v-if="!(d.events || []).length" state="empty" title="暂无校历事件" />
        <view v-for="e in d.events" :key="e.eventId || e.id" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ e.eventType || e.type || '事件' }} {{ e.remark || e.title || '' }}</text>
            <text class="mk__sub">{{ (e.startDate || '').slice(0,10) }} ~ {{ (e.endDate || e.startDate || '').slice(0,10) }}</text>
          </view>
        </view>
        <view class="section-head"><text class="section-head__title">教学周</text></view>
        <view v-for="w in (d.weeks || []).slice(0, 20)" :key="w.weekNo" class="list-row">
          <text class="t-md">第{{ w.weekNo }}周 · {{ w.weekType || '' }}</text>
          <text class="mk__sub">{{ (w.startDate || '').slice(0,10) }} ~ {{ (w.endDate || '').slice(0,10) }}</text>
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
      studentApi.getMyCalendar().then((d) => { this.d = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>
<style scoped>
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
