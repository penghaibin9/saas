<template>
  <span class="sp-sensitive">{{ masked }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  value: { type: [String, Number], default: '' },
  head: { type: Number, default: 3 },
  tail: { type: Number, default: 2 }
})
const masked = computed(() => {
  const s = String(props.value ?? '')
  if (s.length <= props.head + props.tail) return s ? s[0] + '***' : ''
  return s.slice(0, props.head) + '****' + s.slice(s.length - props.tail)
})
</script>
