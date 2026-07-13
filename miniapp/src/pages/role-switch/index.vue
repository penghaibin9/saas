<template>
  <view class="page-wrap">
    <MobileNavBar title="选择工作身份" subtitle="同一账号，多个身份" variant="teacher" :show-back="canBack" />
    <view class="page-pad">
      <view class="rs__intro card">
        <view class="row" style="gap:12px;">
          <view class="rs__avatar">{{ userInitial }}</view>
          <view class="flex-1">
            <text class="t-lg t-bold">{{ user.name }}</text>
            <text v-if="user.tenantName" class="rs__intro-sub">{{ user.tenantName }}</text>
          </view>
        </view>
        <text class="rs__tip">切换身份后，工作台、学生、待办、消息将按该身份的数据范围刷新。</text>
      </view>

      <text class="rs__label">可用身份（{{ identities.length }}）</text>
      <view class="stack">
        <view
          v-for="r in identities"
          :key="r.key"
          class="rs__item card"
          :class="{ 'is-current': r.key === currentRole, 'is-disabled': switching }"
          @click="pick(r.key)"
        >
          <view class="rs__item-icon">{{ r.icon }}</view>
          <view class="flex-1">
            <view class="row-between">
              <text class="t-md t-bold">{{ r.label }}</text>
              <text v-if="r.key === currentRole" class="rs__current">当前</text>
            </view>
            <text class="rs__scope">切换后按该身份的数据范围加载</text>
          </view>
          <text class="rs__arrow">›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { getRoleConfig } from '@/config/roles.config'
import { relaunch, toast } from '@/utils/nav'
import { toastError } from '@/services/request'

const ICONS = { counselor: '👥', mentor: '📘', intern_mentor: '💼', employment: '🎯', academic: '📋', college_admin: '🏛' }

export default {
  data() {
    return { user: {}, currentRole: '', canBack: false, switching: false }
  },
  computed: {
    userInitial() {
      return (this.user.name || '师').slice(0, 1)
    },
    identities() {
      const session = useSessionStore()
      // 只按真实可用身份展示（不再补齐 mock 的全部教师身份，也不显示 mock 的待办/风险数字）
      return (session.availableRoles || []).map((key) => {
        const cfg = getRoleConfig(key)
        return { key, label: cfg.label, icon: ICONS[key] || '🧑‍🏫' }
      })
    }
  },
  onLoad() {
    const session = useSessionStore()
    this.user = session.mockUser || {}
    this.currentRole = session.currentRole
    this.canBack = session.isTeacher && getCurrentPages().length > 1
  },
  methods: {
    async pick(key) {
      if (this.switching) return
      this.switching = true
      uni.showLoading({ title: '切换中…', mask: true })
      try {
        const session = useSessionStore()
        await session.switchRole(key)
        uni.hideLoading()
        toast('已切换为「' + getRoleConfig(key).label + '」')
        relaunch('/pages/teacher/workbench/index')
      } catch (e) {
        uni.hideLoading()
        toastError(e)
      } finally {
        this.switching = false
      }
    }
  }
}
</script>

<style scoped>
.rs__intro { margin-bottom: var(--space-5); }
.rs__avatar {
  width: 44px; height: 44px; border-radius: var(--radius-full);
  background: var(--brand-gradient-teacher); color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: var(--font-size-lg);
}
.rs__intro-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rs__tip { display: block; margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--teacher-50); padding: var(--space-2) var(--space-3); border-radius: var(--radius-base); }
.rs__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-3); }
.rs__item { display: flex; align-items: center; gap: var(--space-3); }
.rs__item.is-current { border: 1px solid var(--teacher-600); }
.rs__item.is-disabled { opacity: 0.6; pointer-events: none; }
.rs__item-icon {
  width: 40px; height: 40px; border-radius: var(--radius-md);
  background: var(--teacher-50); display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.rs__current { font-size: var(--font-size-xs); color: var(--teacher-700); background: var(--teacher-50); padding: 2px 8px; border-radius: var(--radius-full); }
.rs__scope { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.rs__arrow { font-size: var(--font-size-2xl); color: var(--text-tertiary); }
</style>
