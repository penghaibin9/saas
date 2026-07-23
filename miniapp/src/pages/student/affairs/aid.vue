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
          <view v-for="x in d.items" :key="x.applyId" class="list-row col">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md">申请等级：{{ x.applyLevel || '—' }}</text>
                <text class="aid__sub" v-if="x.finalLevel">认定等级：{{ x.finalLevel }}</text>
                <text class="aid__sub" v-if="x.returnReason">意见：{{ x.returnReason }}</text>
              </view>
              <MobileStatusTag :status="x.statusLabel || x.status" />
            </view>
            <text v-if="x.hasPendingObjection" class="hint">异议处理中</text>
            <template v-if="x.canObject">
              <textarea class="ta" v-model="reasons[x.applyId]" placeholder="对公示认定结果有异议（≥5字）" />
              <button class="btn" :disabled="busy" @click="object(x)">提交公示异议</button>
            </template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="如需申请请联系辅导员。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsAidObjection } from '@/services/realApi'

export default {
  data() { return { d: null, state: 'loading', busy: false, reasons: {} } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyAid().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    async object(x) {
      const reason = (this.reasons[x.applyId] || '').trim()
      if (reason.length < 5) {
        uni.showToast({ title: '异议理由至少5字', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await affairsAidObjection({ applyId: x.applyId, reason })
        uni.showToast({ title: '异议已提交', icon: 'success' })
        this.reasons[x.applyId] = ''
        this.load()
      } catch (e) {
        uni.showToast({ title: (e && e.message) || '提交失败', icon: 'none' })
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.aid__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.aid__level { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px; }
.aid__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.col { flex-direction: column; align-items: stretch; gap: 8px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.hint { font-size: 12px; color: #6b7280; }
.ta { width: 100%; min-height: 72px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; box-sizing: border-box; }
.btn { margin-top: 4px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
</style>
