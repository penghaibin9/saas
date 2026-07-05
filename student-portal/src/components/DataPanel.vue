<template>
  <div class="sp-panel">
    <div class="sp-panel__head">{{ title }}</div>
    <StateBlock v-if="!rows.length" type="empty" :text="emptyText" />
    <div v-else class="sp-table-wrap">
      <table class="sp-table">
        <thead>
          <tr><th v-for="(c, i) in columns" :key="i">{{ c }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, ri) in rows" :key="ri">
            <td v-for="(c, ci) in r" :key="ci">{{ c }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import StateBlock from './StateBlock.vue'
defineProps({
  title: { type: String, default: '数据' },
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无数据' }
})
</script>
