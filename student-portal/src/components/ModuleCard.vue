<template>
  <RouterLink class="sp-modcard" :to="to">
    <span class="sp-modcard__icon">{{ icon }}</span>
    <span class="sp-modcard__title">{{ title }}</span>
  </RouterLink>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  icon: { type: String, default: '📦' },
  to: { type: String, default: '/portal/home' }
})
</script>
