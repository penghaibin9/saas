<template>
  <dl class="platform-metrics" aria-label="当前范围数据摘要">
    <div v-for="item in items" :key="item.key || item.label" class="platform-metrics__item" :data-tone="item.tone || 'brand'">
      <dt><span>{{ item.label }}</span><span class="platform-metrics__icon"><AppIcon :name="item.icon || 'kpi'" :size="20" /></span></dt>
      <dd>{{ item.value }}<small v-if="item.unit">{{ item.unit }}</small></dd>
      <p>{{ item.caption }}</p>
    </div>
  </dl>
</template>

<script>
import AppIcon from '@/components/ui/AppIcon.vue'

export default {
  name: 'PlatformMetricStrip',
  components: { AppIcon },
  props: { items: { type: Array, required: true } }
}
</script>

<style scoped>
.platform-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin: 0; }
.platform-metrics__item { --metric-ink: var(--pri); --metric-soft: var(--pri-bg); min-width: 0; padding: var(--space-4) var(--space-5); border: 1px solid var(--card-b); border-radius: var(--r); background: var(--bg-card); box-shadow: var(--s1); }
.platform-metrics__item[data-tone="success"] { --metric-ink: var(--success-700); --metric-soft: var(--ok-l); }
.platform-metrics__item[data-tone="warning"] { --metric-ink: var(--warning-700); --metric-soft: var(--warn-l); }
.platform-metrics__item[data-tone="danger"] { --metric-ink: var(--danger-700); --metric-soft: var(--err-l); }
.platform-metrics dt { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); color: var(--t2); font-size: var(--font-size-sm); }
.platform-metrics__icon { display: grid; place-items: center; flex: none; width: 36px; height: 36px; background: var(--metric-soft); color: var(--metric-ink); border-radius: var(--rs); }
.platform-metrics dd { margin: var(--space-2) 0 0; color: var(--t1); font-size: var(--font-size-3xl); font-weight: var(--font-weight-bold); font-variant-numeric: tabular-nums; line-height: 1.3; overflow-wrap: anywhere; letter-spacing: -.03em; }
.platform-metrics dd small { margin-left: var(--space-2); font-size: var(--font-size-xs); font-weight: normal; letter-spacing: normal; color: var(--t2); }
.platform-metrics p { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); line-height: 1.6; color: var(--t2); }
@media (max-width: 1100px) { .platform-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 480px) { .platform-metrics { gap: var(--space-2); } .platform-metrics__item { padding: var(--space-3); } .platform-metrics dd { font-size: var(--font-size-2xl); } .platform-metrics__icon { width: 28px; height: 28px; } }
</style>
