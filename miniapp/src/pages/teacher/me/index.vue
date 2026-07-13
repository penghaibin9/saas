<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="个人中心" />
    <view class="tme__top">
      <view class="tme__card">
        <view class="tme__avatar">{{ (user.name || '师').slice(0,1) }}</view>
        <view class="flex-1">
          <text class="tme__name">{{ user.name }}</text>
          <text class="tme__sub">{{ user.college }} · {{ user.title }} · 工号 {{ user.workNo }}</text>
        </view>
      </view>
      <!-- 当前身份 + 切换 -->
      <view class="tme__ctx" @click="go('/pages/role-switch/index')">
        <view class="flex-1">
          <text class="tme__ctx-label">当前身份</text>
          <text class="tme__ctx-role">{{ roleConfig.label }} · {{ dataScopeText }}</text>
        </view>
        <text class="tme__ctx-switch">切换（{{ availableCount }}）›</text>
      </view>
    </view>

    <view class="page-pad stack">
      <view class="card">
        <view v-for="row in menu" :key="row.key" class="tme__row" @click="onMenu(row)">
          <text class="tme__row-icon">{{ row.icon }}</text>
          <text class="tme__row-label flex-1">{{ row.label }}</text>
          <text v-if="row.note" class="tme__row-note">{{ row.note }}</text>
          <text class="tme__row-arrow">›</text>
        </view>
      </view>

      <view class="card tme__brand">
        <MobileBrandHeader side="teacher" />
        <text class="tme__brand-ver">{{ versionText }}</text>
      </view>

      <button class="btn btn-ghost btn-block" @click="logout">退出登录</button>
    </view>
    <MobileTabBar side="teacher" active="me" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { ENV } from '@/config/env'
import { go, relaunch, toast } from '@/utils/nav'
export default {
  computed: {
    // 仅演示（mock）模式标注"演示环境"；真实后端/生产构建只显示版本号，避免误导真实用户
    versionText() { return ENV.useMock ? '版本 v1.0.0 · 演示环境（mock 数据）' : '版本 v1.0.0' }
  },
  data() {
    return {
      user: {}, roleConfig: {}, dataScopeText: '', availableCount: 1,
      menu: [
        { key: 'switch', label: '身份切换', icon: '⇄', note: '' },
        { key: 'scope', label: '授权范围', icon: '🗂', note: '' },
        { key: 'log', label: '操作记录', icon: '📋', note: '' },
        { key: 'device', label: '设备管理', icon: '📱', note: '' },
        { key: 'security', label: '安全设置', icon: '🔒', note: '' },
        { key: 'help', label: '帮助与反馈', icon: '💬', note: '' }
      ]
    }
  },
  onShow() {
    const session = useSessionStore()
    this.user = session.mockUser || {}
    this.roleConfig = session.roleConfig
    this.dataScopeText = session.dataScopeText
    this.availableCount = session.availableRoles.length || 1
  },
  methods: {
    go,
    onMenu(row) {
      if (row.key === 'switch') return go('/pages/role-switch/index')
      toast(row.label + '：即将开放')
    },
    logout() {
      uni.showModal({ title: '退出登录', content: '确认退出当前账号？', success: (r) => {
        if (r.confirm) { useSessionStore().logout(); relaunch('/pages/login/index') }
      } })
    }
  }
}
</script>

<style scoped>
.tme__top { background: var(--brand-gradient-teacher); padding: 0 var(--page-padding-mobile) var(--space-5); }
.tme__card { display: flex; align-items: center; gap: var(--space-3); }
.tme__avatar { width: 54px; height: 54px; border-radius: var(--radius-full); background: rgba(255,255,255,0.25); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); }
.tme__name { color: #fff; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.tme__sub { display: block; color: rgba(255,255,255,0.9); font-size: var(--font-size-sm); margin-top: 2px; }
.tme__ctx { display: flex; align-items: center; background: rgba(255,255,255,0.18); border-radius: var(--radius-md); padding: var(--space-3); margin-top: var(--space-4); }
.tme__ctx-label { font-size: var(--font-size-xs); color: rgba(255,255,255,0.85); }
.tme__ctx-role { display: block; color: #fff; font-size: var(--font-size-base); margin-top: 2px; }
.tme__ctx-switch { color: #fff; font-size: var(--font-size-sm); }
.tme__top + .page-pad { margin-top: calc(-1 * var(--space-4)); }
.tme__row { display: flex; align-items: center; gap: var(--space-3); padding: 13px 0; border-bottom: 1px solid var(--border-light); }
.tme__row:last-child { border-bottom: none; }
.tme__row-icon { font-size: 18px; }
.tme__row-label { font-size: var(--font-size-base); color: var(--text-primary); }
.tme__row-note { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tme__row-arrow { color: var(--text-tertiary); font-size: var(--font-size-lg); }
.tme__brand { display: flex; flex-direction: column; gap: var(--space-2); }
.tme__brand-ver { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
