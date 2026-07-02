<template>
  <ul class="stu-timeline">
    <li v-for="(t, i) in items" :key="i" class="stu-timeline__item">
      <span class="stu-timeline__dot" :class="`is-${dotOf(t.type)}`" />
      <div class="stu-timeline__body">
        <div class="stu-timeline__head">
          <span class="stu-timeline__title">{{ t.title }}</span>
          <span class="stu-timeline__op">{{ t.operator }}</span>
        </div>
        <p v-if="t.detail" class="stu-timeline__detail">{{ t.detail }}</p>
        <span class="stu-timeline__time">{{ t.time }}</span>
      </div>
    </li>
    <li v-if="!items.length" class="stu-timeline__empty">暂无主档动态</li>
  </ul>
</template>

<script>
/** StudentTimeline — 主档变更/认证/状态变更/导入导出时间线 */
export default {
  name: 'StudentTimeline',
  props: { items: { type: Array, default: () => [] } },
  methods: {
    dotOf(type) {
      if (type === 'IDENTITY') return 'primary'
      if (type === 'STATUS') return 'warning'
      if (type === 'GUARDIAN') return 'info'
      return 'neutral'
    }
  }
}
</script>

<style scoped>
.stu-timeline { list-style: none; margin: 0; padding: 0; }
.stu-timeline__item { position: relative; padding: 0 0 var(--space-4) var(--space-6); }
.stu-timeline__item::before {
  content: '';
  position: absolute; left: 5px; top: 14px; bottom: 0;
  width: 1px; background: var(--border-base);
}
.stu-timeline__item:last-child::before { display: none; }
.stu-timeline__dot {
  position: absolute; left: 0; top: 5px;
  width: 11px; height: 11px; border-radius: var(--radius-full);
  background: var(--gray-300); box-shadow: 0 0 0 2px var(--bg-card);
}
.stu-timeline__dot.is-primary { background: var(--primary-600); }
.stu-timeline__dot.is-warning { background: var(--warning-500); }
.stu-timeline__dot.is-info { background: var(--info-500); }
.stu-timeline__head { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.stu-timeline__title { font-size: var(--font-size-base); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.stu-timeline__op { font-size: var(--font-size-sm); color: var(--text-secondary); }
.stu-timeline__detail {
  margin: var(--space-1) 0 0;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.stu-timeline__time { display: block; margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.stu-timeline__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); }
</style>
