<template>
  <div class="data-quality-bar">
    <span>数据基准日 {{ quality.baselineDate || '—' }}</span>
    <span class="data-quality-bar__dot" />
    <span>更新 {{ quality.updatedAt || '—' }}</span>
    <span class="data-quality-bar__dot" />
    <span>{{ quality.environment || '—' }}</span>
  </div>
</template>

<script>
export default {
  name: 'DataQualityBar',
  props: {
    quality: {
      type: Object,
      default: () => ({ baselineDate: '', updatedAt: '', environment: '' })
    }
  }
}
</script>

<style scoped>
.data-quality-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.data-quality-bar__dot {
  width: 4px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--border-base);
}
</style>
