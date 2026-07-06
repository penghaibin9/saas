<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学工中心" subtitle="请假 · 资助 · 宿舍 · 我的记录" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <!-- 我的总览 -->
        <view class="af__grid">
          <view class="af__stat"><text class="af__num">{{ data.leaveCount }}</text><text class="af__lbl">请假</text></view>
          <view class="af__stat"><text class="af__num">{{ data.aidApproved }}</text><text class="af__lbl">困难认定</text></view>
          <view class="af__stat"><text class="af__num">{{ data.fundingGranted }}</text><text class="af__lbl">获资助</text></view>
          <view class="af__stat"><text class="af__num">{{ data.riskOpen }}</text><text class="af__lbl">在办风险</text></view>
        </view>

        <!-- 功能入口 -->
        <view class="stack">
          <MobileActionCard title="我的请假" description="请假 / 销假 / 续假记录" icon="📝"
            action-text="查看" @action="go('/pages/student/affairs/leave')" @click="go('/pages/student/affairs/leave')" />
          <MobileActionCard title="我的宿舍" description="床位信息 · 自选宿舍" icon="🏠"
            action-text="查看" @action="go('/pages/student/affairs/dorm')" @click="go('/pages/student/affairs/dorm')" />
          <MobileActionCard title="我的资助" description="困难认定 · 奖助学金" icon="💰"
            :action-text="''" />
          <MobileActionCard title="我的处分" :description="discNote" icon="⚖️" :action-text="''" />
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'
export default {
  data() { return { data: null, disc: null, state: 'loading' } },
  onLoad() { this.load() },
  computed: {
    discNote() {
      if (!this.disc) return '生效中处分数量'
      return this.disc.activeCount > 0 ? `生效中 ${this.disc.activeCount} 条（明细请联系辅导员）` : '暂无生效处分'
    }
  },
  methods: {
    go,
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getAffairsOverview(), studentApi.getMyDiscipline().catch(() => null)])
        .then(([ov, d]) => { this.data = ov; this.disc = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.af__grid { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.af__stat { flex: 1; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) 0; text-align: center; box-shadow: var(--shadow-card); }
.af__num { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); }
.af__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
