<template>
  <!-- UI-P1.5 最小应用壳：路由出口 + 全局 Toast；登录态/退出由 BasePortalLayout 顶栏承载 -->
  <router-view v-slot="{ Component, route }">
    <RouteAccessNotice v-if="route.meta.accessNotice" :key="route.fullPath" :notice="route.meta.accessNotice" />
    <component :is="Component" v-else />
  </router-view>
  <SystemDialogHost />
  <AppToast />
</template>

<script>
import AppToast from '@/components/common/AppToast.vue'
import SystemDialogHost from '@/components/common/SystemDialogHost.vue'
import RouteAccessNotice from '@/views/security/RouteAccessNotice.vue'

export default {
  name: 'App',
  components: { AppToast, SystemDialogHost, RouteAccessNotice }
}
</script>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background: var(--bg-page);
  color: var(--text-primary);
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  line-height: var(--line-height-base);
}
body {
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
* {
  box-sizing: border-box;
}
button,
input,
textarea,
select {
  font: inherit;
}
button {
  -webkit-tap-highlight-color: transparent;
}
::selection {
  background: var(--primary-100);
  color: var(--primary-700);
}
</style>
