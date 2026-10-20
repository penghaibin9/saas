<template>
  <header class="rw-panel-title">
    <span class="rw-panel-icon"><component :is="icon" /></span>
    <div><h2>{{ title }}</h2><small>{{ subtitle }}</small></div>
  </header>
</template>

<script setup>
defineProps({ icon: { type: [Object, Function], required: true }, title: String, subtitle: String })
</script>

<style scoped>
.rw-panel-title { box-sizing: border-box; display: flex; align-items: center; gap: 9px; height: 37px; padding: 4px 11px; border-bottom: 1px solid #0c5586; background: linear-gradient(90deg, #063b70, #04274e 55%, transparent); }
.rw-panel-icon { display: grid; place-items: center; flex: 0 0 22px; width: 22px; height: 22px; color: #38e7ff; }
.rw-panel-icon :deep(svg) { width: 20px; height: 20px; }
h2 { margin: 0; font-size: 16px; line-height: 20px; letter-spacing: 1px; }
small { display: block; margin: 0; color: #7cb7d8; font-size: 8px; line-height: 10px; }
</style>
