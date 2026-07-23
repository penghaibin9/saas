<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学工待办" subtitle="点卡片进入处置；权限与指派人与 PC 一致" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="ta__total">
          <text class="ta__total-n">{{ data.total }}</text>
          <text class="ta__total-l">项学工待办</text>
        </view>
        <view class="ta__empty" v-if="!data.cards.length"><text>暂无待办</text></view>
        <view class="stack">
          <view
            v-for="c in data.cards"
            :key="c.todoType"
            class="ta__card"
            @click="openCard(c)"
          >
            <text class="ta__label">{{ c.label }}</text>
            <view class="ta__right">
              <text class="ta__count">{{ c.count }}</text>
              <text class="ta__go">›</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

const ROUTES = {
  LEAVE_APPROVAL: '/pages/teacher/affairs-leave/index',
  LEAVE_CANCEL: '/pages/teacher/affairs-leave/index',
  LEAVE_OVERDUE: '/pages/teacher/affairs-leave/index',
  LEAVE_EXTENSION: '/pages/teacher/affairs-leave/index',
  AID_APPROVAL: '/pages/teacher/affairs-review/index?type=AID_APPROVAL',
  AID_ADJUST: '/pages/teacher/affairs-review/index?type=AID_ADJUST',
  FUNDING_APPROVAL: '/pages/teacher/affairs-review/index?type=FUNDING_APPROVAL',
  DISCIPLINE_APPROVAL: '/pages/teacher/affairs-review/index?type=DISCIPLINE_APPROVAL',
  DISCIPLINE_REMOVE: '/pages/teacher/affairs-review/index?type=DISCIPLINE_REMOVE',
  RISK_HANDLE: '/pages/teacher/affairs-review/index?type=RISK_HANDLE'
}

export default {
  data() { return { data: null, state: 'loading' } },
  onLoad() { this.load() },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getAffairs().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    openCard(c) {
      const url = ROUTES[c.todoType]
      if (!url) { toast('该类型请在 PC 学工模块处理'); return }
      uni.navigateTo({ url })
    }
  }
}
</script>

<style scoped>
.ta__total { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); display: flex; align-items: baseline; gap: var(--space-2); }
.ta__total-n { font-size: 28px; font-weight: 700; }
.ta__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ta__card { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.ta__label { font-weight: 600; color: var(--text-primary); }
.ta__right { display: flex; align-items: center; gap: 8px; }
.ta__count { font-size: 20px; font-weight: 700; color: var(--brand-primary); }
.ta__go { color: var(--text-tertiary); font-size: 20px; }
</style>
