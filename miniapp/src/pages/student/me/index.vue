<template>
  <view class="page-wrap">
    <view class="me__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="me__navbar"><text class="me__navbar-title">我的</text></view>
      <view class="me__card">
        <view class="avatar-badge is-lg">{{ (user.name || '生').slice(0,1) }}</view>
        <view class="flex-1">
          <view class="row" style="gap:8px;">
            <text class="me__name">{{ user.name }}</text>
            <text class="me__tag">学生</text>
          </view>
          <text class="me__sub">{{ user.className }}{{ user.studentNo ? ' · 学号 ' + user.studentNo : '' }}</text>
        </view>
        <view class="me__edit" @click="toast('出示身份码（短时有效，不含敏感字段）')">
          <text class="me__edit-icon">▣</text>
        </view>
      </view>
    </view>

    <view class="page-pad stack">
      <!-- 我的全周期入口 -->
      <view class="list-group">
        <text class="list-group__title">我的全周期</text>
        <view v-for="(m, i) in lifecycleMenu" :key="m.route" class="list-row" @click="go(m.route)">
          <view class="list-row__icon" :class="rowTone(i)"><text>{{ m.icon }}</text></view>
          <text class="list-row__label">{{ m.label }}</text>
          <text class="list-row__chevron">›</text>
        </view>
      </view>

      <!-- 证照 / 授权 / 隐私 -->
      <view class="list-group">
        <text class="list-group__title">账号与安全</text>
        <view v-for="row in listMenu" :key="row.key" class="list-row" @click="onListMenu(row)">
          <view class="list-row__icon" style="background: var(--info-100); color: var(--info-600);"><text>{{ row.icon }}</text></view>
          <text class="list-row__label">{{ row.label }}</text>
          <text v-if="row.note" class="list-row__value">{{ row.note }}</text>
          <text class="list-row__chevron">›</text>
        </view>
      </view>

      <!-- 品牌 / 版本 -->
      <view class="card me__brand">
        <MobileBrandHeader side="student" />
        <text class="me__brand-ver">{{ versionText }}</text>
      </view>

      <button class="btn btn-ghost btn-block" @click="logout">退出登录</button>
    </view>
    <MobileTabBar side="student" active="me" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { ENV } from '@/config/env'
import { go, relaunch, toast } from '@/utils/nav'
import { studentApi } from '@/services/studentApi'
export default {
  computed: {
    // 仅演示（mock）模式标注"演示环境"；真实后端/生产构建只显示版本号，避免误导真实用户
    versionText() { return ENV.useMock ? '版本 v1.0.0 · 演示环境（mock 数据）' : '版本 v1.0.0' }
  },
  data() {
    return {
      user: {},
      statusBarHeight: 20,
      lifecycleMenu: [
        { label: '我的档案', icon: '📄', route: '/pages/student/profile/index' },
        { label: '迎新报到', icon: '🎒', route: '/pages/student/orientation/index' },
        { label: '教务中心', icon: '📈', route: '/pages/student/academic-affairs/index' },
        { label: '学工中心', icon: '🏫', route: '/pages/student/affairs/index' },
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
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  methods: {
    go, toast,
    rowTone(i) { return ['tone-blue', 'tone-green', 'tone-amber', 'tone-cyan'][i % 4] },
    onListMenu(row) {
      if (row.key === 'privacy') return go('/pages/common/account-security/index')
      if (row.key === 'export') return this.exportData()
      toast(row.label + '：即将开放')
    },
    exportData() {
      uni.showLoading({ title: '正在生成…', mask: true })
      studentApi.exportMyData().then((res) => {
        uni.hideLoading()
        const b64 = res && res.base64
        const name = (res && res.fileName) || 'export.xlsx'
        if (!b64) return toast('导出失败，请重试')
        // #ifdef MP-WEIXIN
        const fs = uni.getFileSystemManager()
        const fp = `${wx.env.USER_DATA_PATH}/${name}`
        fs.writeFile({ filePath: fp, data: b64, encoding: 'base64',
          success: () => uni.openDocument({ filePath: fp, fileType: 'xlsx', showMenu: true,
            fail: () => toast('已生成，请在聊天文件或文件管理中查看') }),
          fail: () => toast('导出失败，请重试') })
        // #endif
        // #ifdef H5
        const bin = atob(b64)
        const arr = new Uint8Array(bin.length)
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
        const blob = new Blob([arr], { type: (res && res.mime) || 'application/octet-stream' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url; link.download = name; link.click()
        URL.revokeObjectURL(url)
        // #endif
      }).catch((e) => { uni.hideLoading(); toast((e && e.message) || '导出失败，请重试') })
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
.me__hero { padding: 0 var(--page-padding-mobile) var(--space-5); }
.me__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.me__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.me__card { position: relative; display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-2); }
.me__name { color: #fff; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.me__tag { font-size: var(--font-size-xs); color: #fff; background: rgba(255,255,255,.22); border: 1px solid rgba(255,255,255,.3); padding: 2px 9px; border-radius: var(--radius-base); }
.me__sub { display: block; color: rgba(255,255,255,0.9); font-size: var(--font-size-sm); margin-top: 4px; }
.me__edit { width: 30px; height: 30px; border-radius: var(--radius-full); background: rgba(255,255,255,0.16); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.me__edit-icon { color: #fff; font-size: 16px; }
.tone-blue { background: var(--primary-100); color: var(--primary-600); }
.tone-green { background: var(--success-100); color: var(--success-600); }
.tone-amber { background: var(--warning-100); color: var(--warning-700); }
.tone-cyan { background: var(--info-100); color: var(--info-600); }
.me__brand { display: flex; flex-direction: column; gap: var(--space-2); }
.me__brand-ver { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
