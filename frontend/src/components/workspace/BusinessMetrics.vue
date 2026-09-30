<template>
  <dl class="business-metrics" aria-label="业务统计">
    <div v-for="item in items" :key="item.key || item.label">
      <dt>{{ item.label }}<span v-if="item.unit === '天'">（天）</span></dt>
      <dd :class="{ attention: Number(item.value) > 0 && ['risk', 'warning'].includes(item.accent) }">{{ item.value ?? '—' }}</dd>
    </div>
  </dl>
</template>
<script setup>
defineProps({ items: { type: Array, default: () => [] } })
</script>
<style scoped>
.business-metrics{display:flex;flex-wrap:wrap;gap:12px 28px;margin:0;padding:14px 0;border-bottom:1px solid var(--line);color:var(--t1)}
.business-metrics>div{min-width:94px;flex:1}.business-metrics dt{font-size:12px;color:var(--t3);line-height:20px}.business-metrics dd{margin:3px 0 0;font-size:25px;line-height:30px;font-weight:650;font-variant-numeric:tabular-nums}.business-metrics .attention{color:var(--danger-600,#d14343)}
@media(max-width:700px){.business-metrics{gap:12px}.business-metrics>div{flex:1 1 26%}}
</style>
