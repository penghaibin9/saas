<template>
  <main class="ix-login">
    <section class="ix-login__panel">
      <div class="ix-login__brand">跃科岗位实习管理平台</div>
      <h1>学生端登录</h1>
      <p>使用学校分配的学生账号进入岗位实习系统。</p>
      <form @submit.prevent="submit">
        <label>学校编码<input v-model.trim="form.tenantCode" autocomplete="organization" placeholder="学校要求时填写" /></label>
        <label>学号 / 登录账号<input v-model.trim="form.loginName" autocomplete="username" required /></label>
        <label>密码<input v-model="form.password" type="password" autocomplete="current-password" required /></label>
        <div v-if="error" class="ix-login__error" role="alert">{{ error }}</div>
        <button type="submit" class="sp-btn sp-btn--block" :disabled="submitting">{{ submitting ? '登录中…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { usePortalConfigStore } from '../stores/portalConfig'

const session = useSessionStore()
const config = usePortalConfigStore()
const router = useRouter()
const route = useRoute()
const submitting = ref(false)
const error = ref('')
const form = reactive({ tenantCode: '', loginName: '', password: '' })

async function submit() {
  if (submitting.value) return
  error.value = ''
  submitting.value = true
  try {
    await session.login(form.loginName, form.password, form.tenantCode)
    await config.load()
    const target = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
      ? route.query.redirect : '/internship'
    await router.replace(target)
  } catch (e) {
    error.value = e?.message || '登录失败，请核对账号和密码'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.ix-login{min-height:100vh;display:grid;place-items:center;padding:24px;background:linear-gradient(145deg,#eef5ff,#f8fbff)}
.ix-login__panel{width:min(420px,100%);padding:34px;background:#fff;border:1px solid #dbe5f4;border-radius:18px;box-shadow:0 22px 60px rgba(38,75,130,.12)}
.ix-login__brand{font-size:13px;color:var(--pri);font-weight:700}.ix-login h1{margin:10px 0 6px;font-size:26px}.ix-login p{margin:0 0 24px;color:var(--t3);font-size:13px}
.ix-login form{display:flex;flex-direction:column;gap:15px}.ix-login label{display:flex;flex-direction:column;gap:6px;color:var(--t2);font-size:13px}.ix-login input{height:44px;border:1px solid #d9e1ec;border-radius:9px;padding:0 12px;font:inherit}.ix-login input:focus{outline:2px solid rgba(47,107,255,.12);border-color:var(--pri)}
.ix-login__error{padding:9px 11px;border-radius:8px;background:#fff1f1;color:#b42318;font-size:12px}
</style>
