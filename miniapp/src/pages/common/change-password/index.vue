<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="修改密码" show-back />
    <view class="page-pad">
      <MobileInlineAlert v-if="isDemo" type="warning" title="演示账号不支持修改密码"
        description="当前登录为演示/mock账号，无真实凭据体系。请使用学校正式账号密码登录后再修改密码。" />

      <template v-else>
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
            {{ submitting ? '提交中…' : '确认修改' }}
          </button>
        </view>
        <text class="cp__hint t-xs t-tertiary">修改后当前登录仍然有效，下次登录请使用新密码。</text>
      </template>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { changePassword } from '@/services/realApi'
import { normalizeError } from '@/services/request'

export default {
  data() {
    return {
      isDemo: true, submitting: false, errorText: '',
      form: { oldPassword: '', newPassword: '', confirmPassword: '' }
    }
  },
  onShow() {
    const uid = String(useSessionStore().identity.userId || '')
    this.isDemo = !uid.startsWith('db-')
  },
  computed: {
    canSubmit() {
      return this.form.oldPassword && this.form.newPassword.length >= 8 &&
        this.form.newPassword === this.form.confirmPassword
    }
  },
  methods: {
    submit() {
      if (this.submitting || !this.canSubmit) return
      this.errorText = ''
      if (this.form.newPassword !== this.form.confirmPassword) {
        this.errorText = '两次输入的新密码不一致'
        return
      }
      this.submitting = true
      changePassword(this.form.oldPassword, this.form.newPassword).then(() => {
        uni.showToast({ title: '密码修改成功', icon: 'success' })
        this.form = { oldPassword: '', newPassword: '', confirmPassword: '' }
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
