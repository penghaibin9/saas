<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="账号与安全" show-back />
    <view class="page-pad stack">
      <view class="section-head"><text class="section-head__title">账号信息</text></view>
      <view class="list-group">
        <view class="list-row"><text class="flex-1 t-md">姓名</text><text class="as__val">{{ info.name || '—' }}</text></view>
        <view class="list-row" v-if="isStudent"><text class="flex-1 t-md">学号</text><text class="as__val">{{ info.studentNo || '—' }}</text></view>
        <view class="list-row" v-if="isStudent"><text class="flex-1 t-md">班级</text><text class="as__val">{{ info.className || '—' }}</text></view>
        <view class="list-row" v-if="isStudent"><text class="flex-1 t-md">手机号</text><text class="as__val">{{ info.phoneMasked || '未登记' }}</text></view>
        <view class="list-row" v-if="!isStudent"><text class="flex-1 t-md">当前身份</text><text class="as__val">{{ info.roleLabel || '—' }}</text></view>
        <view class="list-row" v-if="!isStudent"><text class="flex-1 t-md">数据范围</text><text class="as__val">{{ info.scopeText || '—' }}</text></view>
        <view class="list-row"><text class="flex-1 t-md">所属学校</text><text class="as__val">{{ info.tenantName || '—' }}</text></view>
      </view>

      <view class="section-head"><text class="section-head__title">安全设置</text></view>
      <view class="list-group">
        <view class="list-row" @click="go('/pages/common/change-password/index')">
          <text class="flex-1 t-md">修改密码</text>
          <text class="list-row__chevron">›</text>
        </view>
        <view class="list-row" @click="go('/pages/common/notify-settings/index')">
          <text class="flex-1 t-md">消息通知设置</text>
          <text class="list-row__chevron">›</text>
        </view>
      </view>

      <text class="as__note t-xs t-tertiary">敏感字段已按规则脱敏展示；如信息有误请联系学校管理员核实。</text>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

export default {
  data() { return { info: {}, isStudent: true } },
  onShow() {
    const session = useSessionStore()
    this.isStudent = session.side === 'student'
    if (this.isStudent) {
      studentApi.getProfile().then((p) => {
        this.info = { name: (p.base || {}).name, studentNo: (p.base || {}).studentNo,
          className: (p.org || {}).className, phoneMasked: (p.contact || {}).phone,
          tenantName: (session.mockUser || {}).tenantName }
      }).catch(() => {
        this.info = { name: (session.mockUser || {}).name, tenantName: (session.mockUser || {}).tenantName }
      })
    } else {
      const u = session.mockUser || {}
      this.info = { name: u.name, roleLabel: session.roleConfig.label,
        scopeText: session.dataScopeText, tenantName: u.tenantName }
    }
  },
  methods: { go }
}
</script>

<style scoped>
.as__val { font-size: var(--font-size-base); color: var(--text-secondary); }
.as__note { display: block; margin-top: var(--space-2); }
</style>
