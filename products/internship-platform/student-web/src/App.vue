<template>
  <div class="sp-app">
    <header v-if="session.isLoggedIn" class="ix-head">
      <div>
        <strong>{{ config.brand.schoolName || '学校' }} · 岗位实习</strong>
        <span>学生 PC 端</span>
      </div>
      <div class="ix-head__user">
        <span>{{ session.user?.realName || session.user?.studentNo || '学生' }}</span>
        <button type="button" @click="logout">退出</button>
      </div>
    </header>
    <main :class="{ 'ix-main': session.isLoggedIn }"><router-view /></main>
    <SystemDialogHost />
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import SystemDialogHost from './components/SystemDialogHost.vue'
import { useSessionStore } from './stores/session'
import { usePortalConfigStore } from './stores/portalConfig'
import { useUiStore } from './stores/ui'

const router = useRouter()
const session = useSessionStore()
const config = usePortalConfigStore()
const ui = useUiStore()

onMounted(async () => {
  await session.restore()
  if (session.isLoggedIn) await config.load()
})
async function logout() {
  await session.logout()
  await router.replace('/login')
}
</script>

<style scoped>
.ix-head{position:sticky;top:0;z-index:30;height:64px;padding:0 28px;display:flex;align-items:center;justify-content:space-between;gap:20px;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 1px 4px rgba(29,33,41,.04)}
.ix-head>div:first-child{display:flex;align-items:baseline;gap:10px}.ix-head strong{font-size:17px;color:var(--t1)}.ix-head span{font-size:12px;color:var(--t3)}.ix-head__user{display:flex;align-items:center;gap:12px}.ix-head__user button{border:0;background:none;color:var(--pri);cursor:pointer}.ix-main{max-width:1280px;margin:0 auto;padding:22px}
</style>
