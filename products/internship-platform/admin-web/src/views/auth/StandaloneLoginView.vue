<template>
  <main class="sl-page">
    <section class="sl-card" aria-labelledby="sl-title">
      <div class="sl-brand">跃科岗位实习管理平台</div>
      <h1 id="sl-title">学校管理 / 指导教师登录</h1>
      <p>登录后只进入岗位实习 Standalone，不依赖原 SaaS 前端运行时。</p>
      <form @submit.prevent="submit">
        <label>学校编码<input v-model.trim="tenantCode" autocomplete="organization" placeholder="如已绑定学校可留空" /></label>
        <label>账号<input v-model.trim="loginName" autocomplete="username" required /></label>
        <label>密码<input v-model="password" type="password" autocomplete="current-password" required /></label>
        <div v-if="error" class="sl-error" role="alert">{{ error }}</div>
        <button type="submit" :disabled="loading">{{ loading ? '正在登录…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>

<script>
import { loginWithPassword } from '@/services/http/client'

export default {
  name: 'StandaloneLoginView',
  data() {
    return { tenantCode: '', loginName: '', password: '', loading: false, error: '' }
  },
  methods: {
    async submit() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        await loginWithPassword(this.loginName, this.password, this.tenantCode, { clientType: 'PC' })
        const raw = typeof this.$route.query.redirect === 'string' ? this.$route.query.redirect : ''
        const target = raw.startsWith('/') && !raw.startsWith('/login') ? raw : '/admin/internship'
        await this.$router.replace(target)
      } catch (error) {
        this.error = error?.message || '登录失败，请核对账号、密码和学校编码'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>
