<template>
  <view class="teacher-shell">
    <MobileTeacherHero title="我的" :show-identity="false" />
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="load" />
    <view v-else class="ts-pad">
      <view class="profile"><view class="profile-avatar">{{ (user.name || '师').slice(0,1) }}</view><view class="ts-body"><text class="profile-name">{{ user.name }}</text><text class="ts-muted">{{ user.tenantName }}</text></view><button class="profile-role ts-plain" @click="go('/pages/role-switch/index')">{{ roleConfig.label }}<MobileShellIcon name="chevron-right" tone="gray" :size="14" /></button></view>
        <view class="ts-panel profile-settings">
          <view class="ts-row profile-scope"><MobileShellIcon name="user" :size="25" round /><view class="ts-body"><text class="ts-muted">工作范围</text><text class="ts-row-title">{{ dataScopeText || '以当前业务授权范围为准' }}</text></view></view>
          <button class="ts-row ts-plain profile-setting" @click="go('/pages/role-switch/index')"><MobileShellIcon name="clipboard-check" tone="violet" :size="25" round /><text class="ts-body">身份切换</text><text class="ts-muted">{{ identityCount }}个可用身份</text><MobileShellIcon name="chevron-right" tone="gray" :size="18" /></button>
          <button class="ts-row ts-plain profile-setting" @click="go('/pages/common/account-security/index')"><MobileShellIcon name="shield-check" tone="green" :size="25" round /><text class="ts-body">安全设置</text><MobileShellIcon name="chevron-right" tone="gray" :size="18" /></button>
          <button class="ts-row ts-plain profile-setting" @click="go('/pages/common/help/index')"><MobileShellIcon name="message-dots" tone="amber" :size="25" round /><text class="ts-body">{{ helpEntry.label }}</text><MobileShellIcon name="chevron-right" tone="gray" :size="18" /></button>
        </view>
        <view class="profile-footer"><text class="ts-muted">{{ versionText }}</text><button class="profile-logout ts-plain" @click="logout">退出登录</button></view>
    </view>
    <MobileTeacherTabBar ref="badges" active="me" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { ENV } from '@/config/env'
import { go, relaunch, toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { me } from '@/services/realApi'
import { normalizeError } from '@/services/request'
export default {
  computed: {
    // 仅演示（mock）模式标注"演示环境"；真实后端/生产构建只显示版本号，避免误导真实用户
    versionText() { return ENV.useMock ? '版本 v1.0.0 · 演示环境（mock 数据）' : '版本 v1.0.0' },
  },
  data() {
    return {
      user: {}, roleConfig: {}, dataScopeText: '', identityCount: 0, state: 'loading', loadSeq: 0,
      helpEntry: { key: 'help', label: '帮助与反馈' }
    }
  },
  onShow() { this.load(); this.$refs?.badges?.refresh() },
  onHide() { this.loadSeq++; this.$refs?.badges?.invalidate() },
  onUnload() { this.loadSeq++ },
  methods: {
    async load() {
      const seq = ++this.loadSeq, generation = currentSessionGeneration()
      this.state = 'loading'
      try {
        const identity = await me()
        if (seq !== this.loadSeq || generation !== currentSessionGeneration()) return
        const session = useSessionStore(); session.applyRealUser(identity)
        if (!session.isTeacher) { this.state = 'forbidden'; return }
        this.user = session.mockUser || {}; this.roleConfig = session.roleConfig
        this.dataScopeText = session.dataScopeText; this.identityCount = session.availableRoles.length; this.state = 'ready'
      } catch (error) { if (seq === this.loadSeq && generation === currentSessionGeneration()) this.state = normalizeError(error).pageState || 'error' }
    },
    go,
    logout() {
      uni.showModal({ title: '退出登录', content: '确认退出当前账号？', success: async (r) => {
        if (r.confirm) {
          try { await useSessionStore().logoutCurrentSession() } catch (error) { toast(error?.message || '退出失败，请重试'); return }
          relaunch('/pages/login/teacher/index') }
      } })
    }
  }
}
</script>
<style lang="scss">
@import '@/styles/teacher-shell.scss';
.teacher-shell {
.profile { display: flex; align-items: center; gap: 14px; padding: 34px 0 14px; flex-wrap: wrap; }
.profile-avatar { width: 68px; height: 68px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: #ff978c; color: #fff; font-size: 32px; font-weight: 500; flex-shrink: 0; }
.profile-name { display: block; font-size: 21px; font-weight: 600; line-height: 1.5; margin-bottom: 3px; }
.profile-role { display: flex; align-items: center; gap: 4px; padding: 7px 10px !important; min-height: 36px; border-radius: 20px; background: rgba(255,255,255,.8) !important; max-width: 45%; font-size: 13px; color: #294266; }
.profile-role .shell-icon { transform: rotate(90deg); }
.profile-settings { margin-top: 10px; }
.profile-scope { padding-bottom: 26px !important; margin-bottom: 8px; }
.profile-setting { width: 100%; color: #142440; font-size: 16px; min-height: 84px !important; box-sizing: border-box; }
.profile-footer { text-align: center; padding: 55px 20px 22px; }
.profile-logout { margin: 14px auto 0 !important; padding: 14px 32px !important; min-height: 44px; border-top: 1px solid #e7ecf3 !important; color: #e64c4c; font-size: 15px; text-align: center !important; }
}
</style>
