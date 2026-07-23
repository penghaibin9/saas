<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="谈心谈话" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="list-group" v-if="(d.items || []).length">
          <view v-for="x in d.items" :key="x.talkId" class="list-row col">
            <view class="row-between">
              <text class="flex-1 t-md">{{ x.talkTypeLabel || x.talkType || '谈心谈话' }}</text>
              <MobileStatusTag :status="x.statusLabel || x.status" />
            </view>
            <text class="hint">{{ x.topic || '' }}</text>
            <text class="hint">{{ (x.talkAt || '').slice(0, 16) || '时间待定' }}</text>
            <text v-if="x.needFollow" class="hint warn">需回访跟进</text>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无谈话记录" description="辅导员登记后会同步到这里。" />
        <text v-if="d.detailNote" class="hint foot">{{ d.detailNote }}</text>
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
      studentApi.getMyTalks().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.col { flex-direction: column; align-items: stretch; gap: 6px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.hint { font-size: 12px; color: #6b7280; }
.hint.warn { color: #b45309; }
.foot { display: block; margin-top: 12px; }
</style>
