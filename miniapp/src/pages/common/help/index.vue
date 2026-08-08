<template>
  <view v-if="!helpUrl" class="help-fallback page-wrap">
    <view class="help-fallback__card card">
      <text class="help-fallback__icon">?</text>
      <text class="help-fallback__title">帮助中心尚未配置访问地址</text>
      <text class="help-fallback__desc">
        当前小程序已经接入统一帮助入口，但正式环境还需要配置 VITE_HELP_CENTER_URL，并在微信公众平台登记对应业务域名。
      </text>
      <view class="help-fallback__facts">
        <text>帮助正文仍由 PC 帮助中心统一维护，不在小程序复制第二套内容。</text>
        <text>配置完成后，本页会自动带入当前角色，只展示更相关的帮助。</text>
      </view>
      <button class="btn btn-primary btn-block" @click="back">返回上一页</button>
    </view>
  </view>
  <web-view v-else :src="helpUrl" />
</template>

<script>
import { ENV } from '@/config/env'
import { useSessionStore } from '@/stores/session'

function normalizeHelpRole(session) {
  const code = String(session.currentRole || session.identity?.roleCode || '').toUpperCase()
  if (!session.isTeacher) return 'student'
  if (/SCHOOL_ADMIN|SYSTEM_ADMIN/.test(code)) return 'school-admin'
  if (/ACADEMIC|TEACHING_ADMIN|EDUCATION/.test(code)) return 'academic'
  if (/COUNSELOR|STUDENT_AFFAIRS|HEAD_TEACHER|CLASS_TEACHER/.test(code)) return 'student-affairs'
  return 'teacher'
}

function appendQuery(url, params) {
  const source = String(url || '').trim()
  if (!source) return ''
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
  if (!query) return source
  return `${source}${source.includes('?') ? '&' : '?'}${query}`
}

export default {
  data() {
    return { helpUrl: '' }
  },
  onLoad() {
    const session = useSessionStore()
    this.helpUrl = appendQuery(ENV.helpCenterUrl, {
      role: normalizeHelpRole(session),
      source: 'miniapp'
    })
  },
  methods: {
    back() {
      uni.navigateBack({ delta: 1 })
    }
  }
}
</script>

<style scoped>
.help-fallback {
  min-height: 100vh;
  padding: calc(var(--space-8) + env(safe-area-inset-top)) var(--page-padding-mobile) var(--space-8);
  background: var(--bg-page);
}
.help-fallback__card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-4);
  padding: var(--space-6);
}
.help-fallback__icon {
  width: 48px;
  height: 48px;
  margin: 0 auto;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-100);
  color: var(--primary-600);
  font-size: 24px;
  font-weight: var(--font-weight-semibold);
}
.help-fallback__title {
  text-align: center;
  color: var(--text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}
.help-fallback__desc {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.help-fallback__facts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  border-radius: var(--radius-base);
  background: var(--primary-50);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
</style>
