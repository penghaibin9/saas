<template>
  <main class="se-page">
    <section class="se-card" role="alert" aria-labelledby="se-title">
      <div class="se-code">{{ status }}</div>
      <h1 id="se-title">{{ title }}</h1>
      <p>{{ description }}</p>
      <div class="se-actions">
        <button type="button" class="se-primary" @click="goSafe">{{ primaryLabel }}</button>
        <button v-if="status !== '401'" type="button" @click="goLogin">重新登录</button>
      </div>
    </section>
  </main>
</template>

<script>
import { clearAuthSession } from '@/services/http/client'

export default {
  name: 'StandaloneSecurityErrorView',
  computed: {
    status() {
      const value = String(this.$route.params.status || '500')
      return ['401', '403', '419', '500'].includes(value) ? value : '500'
    },
    title() {
      if (this.status === '403') return '当前身份不能访问该页面'
      if (this.status === '419') return '会话已超时'
      if (this.status === '401') return '请先登录'
      return this.$route.query.reason === 'permission-service'
        ? '权限服务暂不可用'
        : '服务暂不可用'
    },
    description() {
      if (this.status === '403') return '系统已按当前角色和学校授权拦截本页面。你可以返回岗位实习首页，或使用有权限的账号重新登录。'
      if (this.status === '419') return '当前登录会话已过期，请重新登录后继续办理。'
      if (this.status === '401') return '登录后才能进入岗位实习管理端。'
      if (this.$route.query.reason === 'permission-service') return '暂时无法确认当前账号的权限，为避免越权，系统已停止加载业务页面。'
      return '当前页面暂时无法安全加载，请返回岗位实习首页后重试。'
    },
    primaryLabel() {
      return this.status === '401' || this.status === '419' ? '去登录' : '返回岗位实习首页'
    }
  },
  methods: {
    goSafe() {
      if (this.status === '401' || this.status === '419') return this.goLogin()
      this.$router.replace('/admin/internship').catch(() => {})
    },
    goLogin() {
      clearAuthSession()
      const from = typeof this.$route.query.from === 'string' ? this.$route.query.from : '/admin/internship'
      this.$router.replace({ path: '/login', query: { redirect: from } }).catch(() => {})
    }
  }
}
</script>

<style scoped>
.se-page{min-height:100vh;display:grid;place-items:center;padding:24px;background:#f4f7fb}
.se-card{width:min(520px,100%);padding:34px;border:1px solid #dbe3ef;border-radius:16px;background:#fff;box-shadow:0 18px 50px rgba(15,39,70,.08)}
.se-code{font-size:13px;font-weight:700;letter-spacing:.12em;color:#64748b}
h1{margin:10px 0 12px;font-size:24px;color:#0f172a}
p{margin:0;color:#526077;line-height:1.8}
.se-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}
button{padding:9px 16px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#334155;cursor:pointer}
.se-primary{border-color:#315fba;background:#315fba;color:#fff}
</style>
