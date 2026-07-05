<template>
  <div class="sp-center">
    <div class="sp-login">
      <h1>学生服务门户</h1>
      <p class="sp-login__sub">请使用你的学生账号登录（与小程序为同一套账号）</p>

      <div class="sp-field">
        <label>账号</label>
        <input class="sp-input" v-model.trim="loginName" placeholder="学号 / 账号" @keyup.enter="doLogin" />
      </div>
      <div class="sp-field">
        <label>密码</label>
        <input class="sp-input" type="password" v-model="password" placeholder="密码" @keyup.enter="doLogin" />
      </div>
      <div class="sp-error">{{ error }}</div>
      <button class="sp-btn sp-btn--block" :disabled="loading" @click="doLogin">{{ loading ? '登录中…' : '登 录' }}</button>

      <div class="sp-demo">
        <div class="sp-demo__tt">演示体验账号（仅演示环境展示 · 点击只填入账号密码，不自动登录、不绕过登录）</div>
        <button v-for="a in demoAccounts" :key="a.loginName" class="sp-demo__btn" @click="fill(a)">
          {{ a.label }}：{{ a.loginName }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { usePortalConfigStore } from '../../stores/portalConfig'

const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const cfg = usePortalConfigStore()

const loginName = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// 演示体验账号：仅登录页展示、点击只填入，绝不自动登录/绕过。真实登录仍走 /auth/login。
// 正式学校租户不应展示；账号是否可用取决于后端是否已开通该演示学生账号。
const demoAccounts = [
  { label: '演示职业技术学校', loginName: 'student', password: '123456' },
  { label: '试用职业技术学校', loginName: 'student2', password: '123456' }
]
function fill(a) {
  loginName.value = a.loginName
  password.value = a.password
  error.value = ''
}

async function doLogin() {
  if (!loginName.value || !password.value) { error.value = '请输入账号与密码'; return }
  loading.value = true
  error.value = ''
  try {
    await session.login(loginName.value, password.value)
    cfg.reset()
    await cfg.load()
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/portal/home')
  } catch (e) {
    error.value = e?.notStudent ? '请使用学生账号登录学生门户' : (e?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
