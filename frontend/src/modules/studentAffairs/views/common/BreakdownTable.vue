<template>
  <table class="bt">
    <tbody>
      <tr v-for="r in sorted" :key="r.key">
        <td class="bt__label">{{ label(r.key) }}</td>
        <td class="bt__bar">
          <div class="bt__track"><div class="bt__fill" :style="{ width: pct(r) + '%' }"></div></div>
        </td>
        <td class="bt__count">{{ r.count }}</td>
      </tr>
      <tr v-if="!sorted.length"><td colspan="3" class="bt__empty">{{ empty }}</td></tr>
    </tbody>
  </table>
</template>

<script>
export default {
  name: 'BreakdownTable',
  props: {
    rows: { type: Array, default: () => [] },
    labelMap: { type: Object, default: () => ({}) },
    empty: { type: String, default: '暂无数据' }
  },
  computed: {
    sorted() { return [...(this.rows || [])].sort((a, b) => (b.count || 0) - (a.count || 0)) },
    max() { return this.sorted.reduce((m, r) => Math.max(m, r.count || 0), 0) || 1 }
  },
  methods: {
    label(k) { return this.labelMap[k] || k || '未分类' },
    pct(r) { return Math.round((r.count || 0) / this.max * 100) }
  }
}
</script>

<style scoped>
.bt { width: 100%; border-collapse: collapse; }
.bt td { padding: 6px var(--space-2); vertical-align: middle; }
.bt__label { white-space: nowrap; font-size: var(--font-size-sm); }
.bt__bar { width: 100%; }
.bt__track { background: var(--bg-muted, #f1f5f9); border-radius: var(--radius-full); height: 14px; }
.bt__fill { background: var(--color-primary); border-radius: var(--radius-full); height: 14px; min-width: 2px; }
.bt__count { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
.bt__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-4); }
</style>
