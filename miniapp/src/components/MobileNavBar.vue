<template>
  <view class="mnav" :class="{ 'is-brand': variant === 'brand', 'is-teacher': variant === 'teacher' }">
    <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="mnav__bar">
      <view class="mnav__left" @click="onBack">
        <text v-if="canGoBack" class="mnav__back">‹</text>
        <slot name="left" />
      </view>
      <view class="mnav__center">
        <text class="mnav__title">{{ title }}</text>
        <text v-if="subtitle" class="mnav__subtitle">{{ subtitle }}</text>
      </view>
      <view class="mnav__right">
        <slot name="right" />
      </view>
    </view>
  </view>
</template>

<script>
/**
 * MobileNavBar 自定义导航栏（适配状态栏高度）
 * variant: default(白底) | brand(学生蓝渐变) | teacher(教师青绿渐变)
 * beforeBack: 可选异步守卫，返回 false 时阻止离页（用于未保存表单提醒）。
 * ``back`` 是既有正式页面使用的简写，和 ``showBack`` 语义一致，统一在公共组件兼容，
 * 避免页面因为属性名漂移出现空白返回位和死点击。
 */
import { back as navBack } from '@/utils/nav'
import { getStatusBarHeight } from '@/utils/deviceInfo'

const STUDENT_HOME = '/pages/student/home/index'
const TEACHER_HOME = '/pages/teacher/workbench/index'

function defaultFallback(variant) {
  // H5 刷新/消息深链可能只有一层页面栈。显式 fallback 仍有最高优先级；
  // 未声明的正式子页按已验证会话身份返回对应工作台，而不是无条件跳登录。
  try {
    const raw = uni.getStorageSync('gx_session_v1')
    const session = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (session?.logged && session?.isTeacher) return TEACHER_HOME
  } catch (e) {}
  return variant === 'teacher' ? TEACHER_HOME : STUDENT_HOME
}

export default {
  name: 'MobileNavBar',
  props: {
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    showBack: { type: Boolean, default: false },
    back: { type: Boolean, default: false },
    variant: { type: String, default: 'default' },
    beforeBack: { type: Function, default: null },
    fallbackUrl: { type: String, default: '' }
  },
  data() {
    return { statusBarHeight: 20, backing: false }
  },
  created() {
    try {
      this.statusBarHeight = getStatusBarHeight()
    } catch (e) {}
  },
  computed: {
    canGoBack() { return this.showBack || this.back },
    resolvedFallbackUrl() { return this.fallbackUrl || defaultFallback(this.variant) }
  },
  methods: {
    async onBack() {
      if (!this.canGoBack || this.backing) return
      this.backing = true
      try {
        if (this.beforeBack) {
          const allowed = await this.beforeBack()
          if (allowed === false) return
        }
        navBack(this.resolvedFallbackUrl)
      } finally {
        this.backing = false
      }
    }
  }
}
</script>

<style scoped>
.mnav { width: 100%; }
.mnav__bar {
  height: 44px;
  display: flex;
  align-items: center;
  padding: 0 var(--space-3);
  background: var(--bg-card);
}
.mnav.is-brand .mnav__status,
.mnav.is-brand .mnav__bar { background: var(--brand-gradient); }
.mnav.is-teacher .mnav__status,
.mnav.is-teacher .mnav__bar { background: var(--brand-gradient-teacher); }
.mnav__left { width: 64px; display: flex; align-items: center; gap: var(--space-1); }
.mnav__right { width: 64px; display: flex; align-items: center; justify-content: flex-end; }
.mnav__back { font-size: 28px; line-height: 1; color: var(--text-primary); }
.mnav.is-brand .mnav__back,
.mnav.is-teacher .mnav__back { color: #fff; }
.mnav__center { flex: 1; text-align: center; display: flex; flex-direction: column; }
.mnav__title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.mnav__subtitle { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 1px; }
.mnav.is-brand .mnav__title,
.mnav.is-teacher .mnav__title { color: #fff; }
.mnav.is-brand .mnav__subtitle,
.mnav.is-teacher .mnav__subtitle { color: rgba(255,255,255,0.85); }
</style>
