<template>
  <div class="sp-layout">
    <aside class="sp-side">
      <div class="sp-side__brand">
        {{ brand.schoolName || brand.platformName }}
        <small>{{ portalName }}</small>
      </div>
      <nav class="sp-menu">
        <RouterLink v-for="m in menu" :key="m.key" :to="m.to">
          <span>{{ m.icon }}</span><span>{{ m.title }}</span>
        </RouterLink>
      </nav>
    </aside>
    <div class="sp-main">
      <header class="sp-top">
        <div class="sp-top__title">{{ portalName }}</div>
        <div>
          <span class="sp-muted">{{ user?.realName || '同学' }}</span>
          <button class="sp-btn sp-btn--ghost" style="margin-left:12px;height:32px;line-height:30px;" @click="logout">退出</button>
        </div>
      </header>
      <main class="sp-content"><router-view /></main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { buildMenu } from '../platform/menuRegistry'

const router = useRouter()
const cfg = usePortalConfigStore()
const session = useSessionStore()

const menu = computed(() => buildMenu(cfg.config))
const brand = computed(() => cfg.brand)
const portalName = computed(() => cfg.portalName)
const user = computed(() => session.user)

function logout() {
  session.logout()
  cfg.reset()
  router.replace('/login')
}
</script>
