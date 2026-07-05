<template>
  <span class="sp-tag" :class="'sp-tag--' + tone">{{ text }}</span>
</template>

<script setup>
defineProps({
  text: { type: String, default: '' },
  tone: { type: String, default: 'default' } // default / success / warn / danger
})
</script>
