<template>
  <!-- UI-P1.5 最小应用壳：只承载路由出口，不含任何业务 -->
  <router-view />
  <AppToast />
</template>

<script>
import AppToast from '@/components/common/AppToast.vue'

export default {
  name: 'App',
  components: { AppToast }
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
