<template>
  <view class="student-shell">
    <MobileStudentHero title="我的">
      <view class="me__card">
        <view class="me__avatar">{{ (user.name || '同').slice(0,1) }}</view>
        <view class="flex-1">
          <view class="row" style="gap:8px;">
            <text class="me__name">{{ user.name || '同学' }}</text>
            <text class="me__tag">学生</text>
          </view>
          <text v-if="user.className" class="me__sub">{{ user.className }}</text>
          <text v-if="user.studentNo" class="me__sub">学号 {{ maskedStudentNo }}</text>
        </view>

      </view>
      <text class="me__intro">个人资料与账号管理</text>
    </MobileStudentHero>

    <view class="shell-pad">
      <!-- 我的全周期入口 -->
      <view class="shell-panel me__records">
        <view v-for="m in lifecycleMenu" :key="m.route" class="shell-row" @click="go(m.route)">
          <MobileShellIcon :name="m.icon" :tone="m.tone" :size="26" round />
          <view class="shell-row__body"><text class="shell-row__title">{{ m.label }}</text><text class="shell-muted">{{ m.desc }}</text></view>
          <MobileShellIcon name="chevron-right" tone="gray" :size="20" />
        </view>
      </view>

      <!-- 证照 / 授权 / 隐私 -->
      <text class="shell-title me__section">账号与支持</text>
      <view class="shell-panel me__settings">
        <view v-for="row in listMenu" :key="row.key" class="shell-row" @click="onListMenu(row)">
          <MobileShellIcon :name="row.icon" :tone="row.tone" :size="25" round />
          <text class="shell-row__body shell-row__title">{{ row.key === 'export' && exporting ? '正在生成…' : row.label }}</text>
          <MobileShellIcon name="chevron-right" tone="gray" :size="20" />
        </view>
      </view>

      <!-- 品牌 / 版本 -->
      <button class="me__logout" @click="logout">退出登录</button>
      <text class="me__logout-hint">退出后将清除本机登录状态</text>
      <view class="me__foot"><text class="shell-link" @click="go('/pages/student/employment/index')">就业去向</text><text class="me__brand-ver">{{ versionText }}</text></view>
    </view>
    <MobileTabBar side="student" active="me" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { ENV } from '@/config/env'
import { go, relaunch, toast } from '@/utils/nav'
import { studentApi } from '@/services/studentApi'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
export default {
  computed: {
    maskedStudentNo() { const value = String(this.user.studentNo || ''); return value.length > 6 ? value.slice(0, 4) + '****' + value.slice(-2) : value },
    // 仅演示（mock）模式标注"演示环境"；真实后端/生产构建只显示版本号，避免误导真实用户
    versionText() { return ENV.useMock ? '版本 v1.0.0 · 演示环境（mock 数据）' : '版本 v1.0.0' }
  },
  data() {
    return {
      user: {},
      exporting: false,
      statusBarHeight: 20,
      lifecycleMenu: [
        { label: '我的档案', desc: '查看本人资料与学籍信息', icon: 'file-text', tone: 'blue', route: '/pages/student/profile/index' },
        { label: '我的办理', desc: '查看进度、退回原因与办理结果', icon: 'folder', tone: 'violet', route: '/pages/student/my-work/index' }
      ],
      listMenu: [
        { key: 'privacy', label: '隐私与安全', icon: 'shield-check', tone: 'teal' },
        { key: 'export', label: '个人数据导出', icon: 'file-download', tone: 'blue' },
        { key: 'help', label: '帮助与反馈', icon: 'message-dots', tone: 'violet' }
      ]
    }
  },
  onShow() {
    this._pageActive = true
    const session = useSessionStore()
    this.user = session.mockUser || {}
    this.statusBarHeight = getStatusBarHeight()
  },
  onHide() { this._pageActive = false },
  onUnload() { this._pageActive = false; this.user = {} },
  methods: {
    go, toast,
    rowTone(i) { return ['tone-blue', 'tone-green', 'tone-amber', 'tone-cyan'][i % 4] },
    onListMenu(row) {
      if (row.key === 'privacy') return go('/pages/common/account-security/index')
      if (row.key === 'export') return this.exportData()
      if (row.key === 'help') return go('/pages/common/help/index')

    },
    exportData() {
      if (this.exporting) return
      this.exporting = true
      const generation = currentSessionGeneration()
      uni.showLoading({ title: '正在生成…', mask: true })
      return studentApi.exportMyData().then((res) => {
        uni.hideLoading()
        if (!this._pageActive || generation !== currentSessionGeneration()) return
        const b64 = res && res.base64
        const name = (res && res.fileName) || 'export.xlsx'
        if (!b64) return toast('导出失败，请重试')
        // #ifdef MP-WEIXIN
        const fs = uni.getFileSystemManager()
        const fp = `${wx.env.USER_DATA_PATH}/${name}`
        fs.writeFile({ filePath: fp, data: b64, encoding: 'base64',
          success: () => uni.openDocument({ filePath: fp, fileType: 'xlsx', showMenu: true,
            fail: () => toast('文件打开失败，请重新导出后重试') }),
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
      }).catch((e) => { uni.hideLoading(); if (this._pageActive && generation === currentSessionGeneration()) toast((e && e.message) || '导出失败，请重试') })
        .finally(() => { this.exporting = false })
    },
    logout() {
      uni.showModal({ title: '退出登录', content: '确认退出当前账号？', success: async (r) => {
        if (r.confirm) {
          try { await useSessionStore().logoutCurrentSession() } catch (error) { toast(error?.message || '退出失败，请重试'); return }
          relaunch('/pages/login/student/index') }
      } })
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/student-shell.scss';
.me__avatar { width:66px; height:66px; border-radius:20px; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.3); color:#fff; display:flex; align-items:center; justify-content:center; font-size:29px; font-weight:600; flex-shrink:0; }
.me__intro { display:block; margin-top:18px; font-size:13px; color:#fff; }
.me__records, .me__settings { padding-top:4px; padding-bottom:4px; }
.me__records .shell-row { min-height:94px; }
.me__settings .shell-row { min-height:78px; }
.me__section { display:block; margin:22px 2px 12px; }
.me__logout { margin-top:24px; border:1px solid #ed6868; border-radius:12px; background:#fff; color:#df4141; font-size:16px; height:46px; line-height:46px; font-weight:600; }
.me__logout::after { border:0; }
.me__logout-hint { display:block; text-align:center; color:#788397; font-size:12px; margin-top:8px; }
.me__foot { display:flex; justify-content:center; align-items:center; gap:16px; margin-top:12px; }
.me__hero { padding: 0 var(--page-padding-mobile) var(--space-5); }
.me__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.me__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.me__card { position: relative; display: flex; align-items: center; gap:16px; margin-top:20px; }
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
