<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学业预警" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <MobileGlobalState v-if="!d.items.length" state="empty" title="暂无学业预警" description="保持良好学业状态，继续加油。" />
        <view class="list-group" v-else>
          <view v-for="w in d.items" :key="w.warningId" class="list-row wn__row">
            <view class="wn__level" :class="'is-' + (w.level || 'low').toLowerCase()">{{ levelText(w.level) }}</view>
            <view class="flex-1">
              <text class="t-md t-bold">{{ typeText(w.warnType) }}</text>
              <text class="wn__reason">{{ w.reason || '—' }}</text>
            </view>
            <MobileStatusTag :status="w.status" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'

const LEVEL_TEXT = { HIGH: '高', MEDIUM: '中', LOW: '低' }
const TYPE_TEXT = { MULTI_FAIL: '多科挂科预警' }

export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    levelText(l) { return LEVEL_TEXT[l] || l || '提示' },
    typeText(t) { return TYPE_TEXT[t] || t || '学业预警' },
    load() {
      this.state = 'loading'
      studentApi.getMyWarnings().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.wn__row { align-items: flex-start; }
.wn__level { flex-shrink: 0; width: 44px; height: 44px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); font-weight: 700; color: #fff; margin-right: var(--space-3); }
.wn__level.is-low { background: #eab308; }
.wn__level.is-medium { background: #f97316; }
.wn__level.is-high { background: var(--danger-600); }
.wn__reason { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
</style>
