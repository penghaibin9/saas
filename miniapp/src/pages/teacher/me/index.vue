<template>
  <view class="page-wrap">
    <view class="tme__hero hero-band is-teacher">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="tme__navbar"><text class="tme__navbar-title">我的</text></view>
      <view class="tme__card">
        <view class="avatar-badge is-lg">{{ (user.name || '师').slice(0,1) }}</view>
        <view class="flex-1">
          <view class="row" style="gap:8px;">
            <text class="tme__name">{{ user.name }}</text>
            <text class="tme__tag" @click.stop="go('/pages/role-switch/index')">{{ roleConfig.label }} ▾</text>
          </view>
          <text class="tme__sub">{{ subText }}</text>
        </view>
        <view class="tme__edit"><text class="tme__edit-icon">✎</text></view>
      </view>
    </view>

    <view class="page-pad stack">
      <view class="list-group">
        <text class="list-group__title">我的工作</text>
        <view v-for="row in menu" :key="row.key" class="list-row" @click="onMenu(row)">
          <view class="list-row__icon" :class="rowTone(row.key)"><text>{{ row.icon }}</text></view>
          <text class="list-row__label">{{ row.label }}</text>
          <text v-if="row.note" class="list-row__value">{{ row.note }}</text>
          <text class="list-row__chevron">›</text>
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
    versionText() { return ENV.useMock ? '版本 v1.0.0 · 演示环境（mock 数据）' : '版本 v1.0.0' },
    // 教师无后端档案接口，头部改用真实的租户 + 数据范围，避免展示 mock 的学院/职称/工号
    subText() {
      const parts = []
      if (this.user && this.user.tenantName) parts.push(this.user.tenantName)
      if (this.dataScopeText) parts.push('数据范围 · ' + this.dataScopeText)
      return parts.join(' · ') || '教师'
    }
  },
  data() {
    return {
      user: {}, roleConfig: {}, dataScopeText: '', statusBarHeight: 20,
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
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  methods: {
    go,
    rowTone(key) {
      const map = { switch: 'tone-blue', scope: 'tone-green', log: 'tone-green', device: 'tone-amber', security: 'tone-cyan', help: 'tone-gray' }
      return map[key] || 'tone-gray'
    },
    onMenu(row) {
      if (row.key === 'switch') return go('/pages/role-switch/index')
      if (row.key === 'security') return go('/pages/common/account-security/index')
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
.tme__hero { padding: 0 var(--page-padding-mobile) var(--space-5); }
.tme__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.tme__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.tme__card { position: relative; display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-2); }
.tme__name { color: #fff; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.tme__tag { font-size: var(--font-size-xs); color: #fff; background: rgba(255,255,255,.22); border: 1px solid rgba(255,255,255,.3); padding: 2px 9px; border-radius: var(--radius-base); }
.tme__sub { display: block; color: rgba(255,255,255,0.9); font-size: var(--font-size-sm); margin-top: 4px; }
.tme__edit { width: 30px; height: 30px; border-radius: var(--radius-full); background: rgba(255,255,255,0.16); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tme__edit-icon { color: #fff; font-size: 15px; }
.tone-blue { background: var(--primary-100); color: var(--primary-600); }
.tone-green { background: var(--success-100); color: var(--success-600); }
.tone-amber { background: var(--warning-100); color: var(--warning-700); }
.tone-cyan { background: var(--info-100); color: var(--info-600); }
.tone-gray { background: var(--gray-100); color: var(--gray-600); }
.tme__brand { display: flex; flex-direction: column; gap: var(--space-2); }
.tme__brand-ver { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
