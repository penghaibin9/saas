<template>
  <main class="sl-page">
    <section class="sl-card" aria-labelledby="sl-title">
      <div class="sl-brand">跃科岗位实习管理平台</div>
      <h1 id="sl-title">学校管理 / 指导教师登录</h1>
      <p>请使用学校分配的账号登录，进入本人待办与实习办理。</p>
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
import { loginWithPassword, request } from '@/services/http/client'
import { getVisibleNavPlan } from '@/config/navPlan'
import { clearPermissionPatterns } from '@/security/permissionGate'
import { getAuthContext, refreshLastActive } from '@/security/auth/auth.context'

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
        const result = await loginWithPassword(this.loginName, this.password, this.tenantCode, { clientType: 'PC' })
        // 本人重新登录后重新读取当前权限，避免沿用已超时身份的活跃时间与页面门禁缓存。
        clearPermissionPatterns()
        getAuthContext()
        refreshLastActive()
        if (result.mustChangePassword) return await this.$router.replace('/account/security')
        const ctx = await request('/rbac/current-context')
        const group = getVisibleNavPlan(ctx)[0]
        const firstPath = group?.children?.[0]?.children?.[0]?.path || group?.children?.[0]?.path || '/security/403'
        const raw = typeof this.$route.query.redirect === 'string' ? this.$route.query.redirect : ''
        const target = raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/login') && raw !== '/admin/internship' ? raw : firstPath
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
