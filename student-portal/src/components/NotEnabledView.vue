<template>
  <div class="sp-center">
    <div class="sp-empty-card">
      <div class="sp-empty-icon">🔒</div>
      <h2>学生门户暂未开通</h2>
      <p>你所在学校尚未开通「学生 PC 服务门户」，请联系学校管理员开通后再访问。</p>
      <button class="sp-btn" @click="logout">退出登录</button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { usePortalConfigStore } from '../stores/portalConfig'

const router = useRouter()
const session = useSessionStore()
const cfg = usePortalConfigStore()

function logout() {
  session.logout()
  cfg.reset()
  router.replace('/login')
}
</script>
