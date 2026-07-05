<template>
  <div class="sp-panel">
    <div class="sp-panel__head">待办事项</div>
    <StateBlock v-if="!items.length" type="empty" text="暂无待办" />
    <ul v-else class="sp-todo">
      <li v-for="(t, i) in items" :key="i">
        <span class="sp-todo__title">{{ t.title || t.name || '待办事项' }}</span>
        <StatusTag :text="t.statusLabel || t.status || '待处理'" tone="warn" />
      </li>
    </ul>
  </div>
</template>

<script setup>
import StateBlock from './StateBlock.vue'
import StatusTag from './StatusTag.vue'
defineProps({ items: { type: Array, default: () => [] } })
</script>
