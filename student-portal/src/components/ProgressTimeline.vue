<template>
  <div class="sp-panel">
    <div class="sp-panel__head">阶段进度</div>
    <StateBlock v-if="!steps.length" type="empty" text="暂无进度信息" />
    <ol v-else class="sp-timeline">
      <li v-for="(s, i) in steps" :key="i" :class="{ 'is-done': s.done }">
        <span class="sp-timeline__dot" />
        <span class="sp-timeline__label">{{ s.label || s.title || ('阶段' + (i + 1)) }}</span>
      </li>
    </ol>
  </div>
</template>

<script setup>
import StateBlock from './StateBlock.vue'
defineProps({ steps: { type: Array, default: () => [] } })
</script>
