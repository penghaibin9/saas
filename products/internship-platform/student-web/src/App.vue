<template>
  <div class="sp-app">
    <PortalLayoutV5 v-if="session.isLoggedIn" @logout="logout"><router-view /></PortalLayoutV5>
    <router-view v-else />
    <SystemDialogHost />
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PortalLayoutV5 from './layouts/PortalLayoutV5.vue'
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
