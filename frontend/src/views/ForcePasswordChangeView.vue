<template>
  <main class="force-page">
    <section class="force-card" aria-labelledby="force-password-title">
      <div class="security-mark" aria-hidden="true">盾</div>
      <p class="eyebrow">ACCOUNT SECURITY</p>
      <h1 id="force-password-title">首次登录，请先修改初始密码</h1>
      <p class="intro">在完成改密前，系统不会开放教务、学工、实习、毕设等业务操作。此限制由服务端强制执行，关闭页面或直接输入业务地址也不能绕过。</p>

      <form @submit.prevent="submit">
        <label for="old-password">当前密码</label>
        <input id="old-password" v-model="form.oldPassword" type="password" autocomplete="current-password" placeholder="请输入当前初始密码">

        <label for="new-password">新密码</label>
        <input id="new-password" v-model="form.newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位，避免与当前密码相同">

        <label for="confirm-password">确认新密码</label>
        <input id="confirm-password" v-model="form.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入新密码">

        <ul class="rules" aria-label="密码要求">
          <li :class="{ ok: form.newPassword.length >= 8 }">至少 8 位字符</li>
          <li :class="{ ok: form.newPassword && form.newPassword !== form.oldPassword }">不能与当前密码相同</li>
          <li :class="{ ok: form.confirmPassword && form.confirmPassword === form.newPassword }">两次新密码输入一致</li>
        </ul>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" type="submit" :disabled="loading">{{ loading ? '正在修改…' : '修改密码并重新登录' }}</button>
        <button class="secondary" type="button" :disabled="loading" @click="leave">退出当前账号</button>
      </form>

      <p class="footnote">如果你不知道当前初始密码，请联系本校系统管理员重置；不要把密码发送给技术支持人员。</p>
    </section>
  </main>
</template>

<script>
import { clearAuthSession, logoutRemote, request } from '@/services/http/client'
import { toast } from '@/utils/toast'

export default {
  name: 'ForcePasswordChangeView',
  data() {
    return {
      loading: false,
      error: '',
      form: { oldPassword: '', newPassword: '', confirmPassword: '' }
    }
  },
  methods: {
    async submit() {
      this.error = ''
      if (!this.form.oldPassword) {
        this.error = '请输入当前密码'
        return
      }
      if (this.form.newPassword.length < 8) {
        this.error = '新密码至少 8 位'
        return
      }
      if (this.form.newPassword === this.form.oldPassword) {
        this.error = '新密码不能与当前密码相同'
        return
      }
      if (this.form.newPassword !== this.form.confirmPassword) {
        this.error = '两次输入的新密码不一致'
        return
      }
      this.loading = true
      try {
        const result = await request('/auth/change-password', {
          method: 'POST',
          body: { oldPassword: this.form.oldPassword, newPassword: this.form.newPassword }
        })
        if (!result?.success) throw new Error('修改密码未成功，请稍后重试')
        // 后端会清 must_change_password、提升用户版本并吊销 refresh。这里主动清掉旧 access，
        // 强制重新登录，确保新会话拿到最新权限/身份版本，绝不继续复用初始密码会话。
        clearAuthSession()
        toast.success('密码已修改，请使用新密码重新登录')
        await this.$router.replace('/login')
      } catch (e) {
        this.error = e?.message || '修改密码失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    async leave() {
      await logoutRemote()
      await this.$router.replace('/login')
    }
  }
}
</script>

<style scoped>
* { box-sizing: border-box; }
.force-page { min-height: 100vh; display: grid; place-items: center; padding: 32px 18px; color: #10233f; background: radial-gradient(circle at 50% 0, #eaf3ff 0, transparent 42%), #f4f7fb; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.force-card { width: min(520px, 100%); padding: 38px 42px 34px; border: 1px solid #dfe7f1; border-radius: 22px; background: #fff; box-shadow: 0 28px 80px -42px rgba(16,35,63,.42); }
.security-mark { display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 20px; border-radius: 15px; color: #fff; background: linear-gradient(135deg, #2f70ea, #1749b2); font-size: 18px; font-weight: 800; }
.eyebrow { margin: 0 0 8px; color: #2f70ea; font-size: 11px; font-weight: 800; letter-spacing: .14em; }
h1 { margin: 0; font-size: 28px; line-height: 1.35; letter-spacing: -.02em; }
.intro { margin: 14px 0 24px; color: #64748b; font-size: 13px; line-height: 1.8; }
label { display: block; margin: 15px 0 7px; color: #34465f; font-size: 12px; font-weight: 700; }
input { width: 100%; height: 46px; padding: 0 13px; border: 1px solid #d9e2ec; border-radius: 10px; outline: none; color: #10233f; font: inherit; }
input:focus { border-color: #2f70ea; box-shadow: 0 0 0 3px rgba(47,112,234,.12); }
.rules { display: grid; gap: 6px; margin: 16px 0 0; padding: 0; list-style: none; color: #8492a6; font-size: 11px; }
.rules li::before { content: '○'; margin-right: 7px; }.rules li.ok { color: #176b42; }.rules li.ok::before { content: '✓'; }
.error { margin: 15px 0 0; padding: 10px 12px; border-radius: 9px; color: #b42318; background: #fff1f0; font-size: 12px; }
button { width: 100%; height: 46px; border-radius: 10px; font: inherit; font-size: 13px; font-weight: 750; cursor: pointer; }
.primary { margin-top: 18px; border: 0; color: #fff; background: linear-gradient(135deg, #2f70ea, #1f56c9); }
.secondary { margin-top: 10px; border: 1px solid #dce4ee; color: #536780; background: #fff; }
button:disabled { opacity: .6; cursor: wait; }
.footnote { margin: 20px 0 0; padding-top: 18px; border-top: 1px solid #edf1f5; color: #8795a8; font-size: 11px; line-height: 1.65; }
@media (max-width: 560px) { .force-page { place-items: start center; padding-top: 22px; }.force-card { padding: 28px 22px 26px; border-radius: 17px; }h1 { font-size: 24px; } }
</style>
