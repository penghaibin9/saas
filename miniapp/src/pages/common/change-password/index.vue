<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="修改密码" :show-back="!forced" />
    <view class="page-pad">
      <MobileInlineAlert v-if="isDemo" type="warning" title="当前账号不支持修改密码"
        description="当前登录不是学校真实数据库账号。请退出后使用学校正式账号密码登录。" />

      <template v-else>
        <MobileInlineAlert v-if="forced" type="warning" title="首次登录必须先修改初始密码"
          description="完成改密前，服务端不会开放任何业务操作；修改成功后需要使用新密码重新登录。" />
        <view class="card stack-sm">
          <view class="cp__field">
            <text class="cp__label">原密码</text>
            <input class="cp__input" v-model="form.oldPassword" password placeholder="请输入当前密码" placeholder-class="cp__ph" />
          </view>
          <view class="cp__field">
            <text class="cp__label">新密码</text>
            <input class="cp__input" v-model="form.newPassword" password placeholder="至少8位" placeholder-class="cp__ph" />
          </view>
          <view class="cp__field">
            <text class="cp__label">确认新密码</text>
            <input class="cp__input" v-model="form.confirmPassword" password placeholder="再次输入新密码" placeholder-class="cp__ph" />
          </view>
          <text v-if="errorText" class="cp__error">{{ errorText }}</text>
          <button class="btn btn-primary" :disabled="submitting || !canSubmit" @click="submit">
            {{ submitting ? '提交中…' : '确认修改并重新登录' }}
          </button>
        </view>
        <text class="cp__hint t-xs t-tertiary">密码修改成功后当前会话会立即清除，请使用新密码重新登录。</text>
      </template>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { changePassword } from '@/services/realApi'
import { normalizeError } from '@/services/request'
import { relaunch } from '@/utils/nav'

export default {
  data() {
    return {
      isDemo: true, forced: false, submitting: false, errorText: '',
      form: { oldPassword: '', newPassword: '', confirmPassword: '' }
    }
  },
  onLoad(options = {}) {
    this.forced = String(options.forced || '') === '1'
  },
  onShow() {
    const uid = String(useSessionStore().identity.userId || '')
    this.isDemo = !uid.startsWith('db-')
  },
  computed: {
    canSubmit() {
      return this.form.oldPassword && this.form.newPassword.length >= 8 &&
        this.form.newPassword !== this.form.oldPassword &&
        this.form.newPassword === this.form.confirmPassword
    }
  },
  methods: {
    submit() {
      if (this.submitting || !this.canSubmit) return
      this.errorText = ''
      if (this.form.newPassword === this.form.oldPassword) {
        this.errorText = '新密码不能与当前密码相同'
        return
      }
      if (this.form.newPassword !== this.form.confirmPassword) {
        this.errorText = '两次输入的新密码不一致'
        return
      }
      this.submitting = true
      changePassword(this.form.oldPassword, this.form.newPassword).then(() => {
        const session = useSessionStore()
        const loginRoute = session.isTeacher ? '/pages/login/teacher/index' : '/pages/login/student/index'
        // 后端已清 must_change_password、提升账号版本并吊销 refresh。小程序主动清理旧 access/
        // 身份快照，避免继续复用改密前会话；session.logout 同时清强制改密导航锁。
        session.logout()
        uni.showToast({ title: '密码修改成功，请重新登录', icon: 'success' })
        setTimeout(() => relaunch(loginRoute), 500)
      }).catch((e) => {
        this.errorText = e && e.biz ? normalizeError(e).text : '修改失败，请稍后重试'
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.cp__field { display: flex; flex-direction: column; gap: 6px; }
.cp__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.cp__input { height: 42px; line-height: 42px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.cp__ph { color: var(--text-tertiary); }
.cp__error { display: block; font-size: var(--font-size-sm); color: var(--danger-600); }
.cp__hint { display: block; margin-top: var(--space-3); }
</style>