<template>
  <div class="sp-state" :class="'sp-state--' + type">
    <span class="sp-state__icon">{{ icon }}</span>
    <span>{{ text }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  type: { type: String, default: 'empty' }, // loading / empty / error
  text: { type: String, default: '' }
})
const icon = computed(() => ({ loading: '⏳', empty: '📭', error: '⚠️' }[props.type] || '📭'))
</script>
