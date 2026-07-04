<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="个人中心" />
    <view class="me__top">
      <view class="me__card">
        <view class="me__avatar">{{ (user.name || '生').slice(0,1) }}</view>
        <view class="flex-1">
          <text class="me__name">{{ user.name }}</text>
          <text class="me__sub">{{ user.className }} · {{ user.studentNo }}</text>
        </view>
        <view class="me__qr" @click="toast('出示身份码（短时有效，不含敏感字段）')">
          <text class="me__qr-icon">▣</text>
          <text class="me__qr-txt">身份码</text>
        </view>
      </view>
    </view>

    <view class="page-pad stack">
      <!-- 我的全周期入口 -->
      <view class="card">
        <text class="card-title">我的全周期</text>
        <view class="me__grid">
          <view v-for="m in lifecycleMenu" :key="m.route" class="me__grid-item" @click="go(m.route)">
            <view class="me__grid-icon">{{ m.icon }}</view>
            <text class="me__grid-label">{{ m.label }}</text>
          </view>
        </view>
      </view>

      <!-- 证照 / 授权 / 隐私 -->
      <view class="card">
        <view v-for="row in listMenu" :key="row.key" class="me__row" @click="toast(row.label + '（演示）')">
          <text class="me__row-icon">{{ row.icon }}</text>
          <text class="me__row-label flex-1">{{ row.label }}</text>
          <text v-if="row.note" class="me__row-note">{{ row.note }}</text>
          <text class="me__row-arrow">›</text>
        </view>
      </view>

      <!-- 品牌 / 版本 -->
      <view class="card me__brand">
        <MobileBrandHeader side="student" />
        <text class="me__brand-ver">版本 v1.0.0 · 演示环境（mock 数据）</text>
      </view>

      <button class="btn btn-ghost btn-block" @click="logout">退出登录</button>
    </view>
    <MobileTabBar side="student" active="me" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { go, relaunch, toast } from '@/utils/nav'
export default {
  data() {
    return {
      user: {},
      lifecycleMenu: [
        { label: '我的档案', icon: '📄', route: '/pages/student/profile/index' },
        { label: '迎新报到', icon: '🎒', route: '/pages/student/orientation/index' },
        { label: '学业进度', icon: '📈', route: '/pages/student/academic/index' },
        { label: '岗位实习', icon: '💼', route: '/pages/student/internship/index' },
        { label: '毕业设计', icon: '📘', route: '/pages/student/graduation/index' },
        { label: '就业去向', icon: '🎯', route: '/pages/student/employment/index' },
        { label: '我的申请', icon: '🗂', route: '/pages/student/my-applications/index' },
        { label: '在校服务', icon: '🛎', route: '/pages/student/campus-service/index' }
      ],
      listMenu: [
        { key: 'card', label: '学生证 / 身份码', icon: '🪪', note: '' },
        { key: 'material', label: '材料证照', icon: '📎', note: '' },
        { key: 'parent', label: '家长授权', icon: '👨‍👩‍👧', note: '未授权' },
        { key: 'privacy', label: '隐私与安全', icon: '🔒', note: '' },
        { key: 'export', label: '个人数据导出', icon: '⬇', note: '' },
        { key: 'help', label: '帮助与反馈', icon: '💬', note: '' }
      ]
    }
  },
  onShow() {
    const session = useSessionStore()
    this.user = session.mockUser || {}
  },
  methods: {
    go, toast,
    logout() {
      uni.showModal({ title: '退出登录', content: '确认退出当前演示账号？', success: (r) => {
        if (r.confirm) { useSessionStore().logout(); relaunch('/pages/login/index') }
      } })
    }
  }
}
</script>

<style scoped>
.me__top { background: var(--brand-gradient); padding: 0 var(--page-padding-mobile) var(--space-5); }
.me__card { display: flex; align-items: center; gap: var(--space-3); }
.me__avatar { width: 54px; height: 54px; border-radius: var(--radius-full); background: rgba(255,255,255,0.25); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); }
.me__name { color: #fff; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.me__sub { display: block; color: rgba(255,255,255,0.9); font-size: var(--font-size-sm); margin-top: 2px; }
.me__qr { display: flex; flex-direction: column; align-items: center; background: rgba(255,255,255,0.2); padding: var(--space-2); border-radius: var(--radius-md); }
.me__qr-icon { color: #fff; font-size: 22px; }
.me__qr-txt { color: #fff; font-size: 11px; }
.me__top + .page-pad { margin-top: calc(-1 * var(--space-4)); }
.me__grid { display: flex; flex-wrap: wrap; margin-top: var(--space-2); }
.me__grid-item { width: 25%; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: var(--space-3) 0; }
.me__grid-icon { font-size: 26px; }
.me__grid-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.me__row { display: flex; align-items: center; gap: var(--space-3); padding: 12px 0; border-bottom: 1px solid var(--border-light); }
.me__row:last-child { border-bottom: none; }
.me__row-icon { font-size: 18px; }
.me__row-label { font-size: var(--font-size-base); color: var(--text-primary); }
.me__row-note { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.me__row-arrow { color: var(--text-tertiary); font-size: var(--font-size-lg); }
.me__brand { display: flex; flex-direction: column; gap: var(--space-2); }
.me__brand-ver { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
