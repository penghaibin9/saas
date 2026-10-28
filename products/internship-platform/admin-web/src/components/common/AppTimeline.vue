<template>
  <ul class="app-timeline">
    <li v-for="(item, i) in items" :key="item.id || i" class="app-timeline__item">
      <span class="app-timeline__dot" :class="`is-${item.type || 'default'}`" />
      <div class="app-timeline__content">
        <div class="app-timeline__head">
          <span class="app-timeline__title">{{ item.title }}</span>
          <AppStatusTag v-if="item.status" :status="item.status" />
        </div>
        <div class="app-timeline__meta">
          <span v-if="item.time">{{ item.time }}</span>
          <span v-if="item.module" class="app-timeline__module">{{ item.module }}</span>
          <span v-if="item.operator">处理人：{{ item.operator }}</span>
        </div>
        <div v-if="item.description" class="app-timeline__desc">{{ item.description }}</div>
        <slot name="item-extra" :item="item" :index="i" />
      </div>
    </li>
  </ul>
</template>

<script>
import AppStatusTag from './AppStatusTag.vue'

/**
 * AppTimeline 时间线（学生360 / 流程记录 / 操作记录通用）
 * Props:
 *  - items: [{ id?, time, title, module?（来源模块）, operator?, status?（状态码）,
 *              description?, type? ('success'|'warning'|'danger'|'primary'|'default') }]
 * Slots: item-extra（每项附加内容，作用域插槽 { item, index }）
 */
export default {
  name: 'AppTimeline',
  components: { AppStatusTag },
  props: {
    items: { type: Array, required: true }
  }
}
</script>

<style scoped>
.app-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.app-timeline__item {
  position: relative;
  padding: 0 0 var(--space-5) var(--space-6);
}
.app-timeline__item::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: 0;
  width: 1px;
  background: var(--border-base);
}
.app-timeline__item:last-child::before {
  display: none;
}
.app-timeline__dot {
  position: absolute;
  left: 0;
  top: 5px;
  width: 11px;
  height: 11px;
  border-radius: var(--radius-full);
  background: var(--gray-300);
  border: 2px solid var(--bg-card);
  box-shadow: 0 0 0 1px var(--border-base);
}
.app-timeline__dot.is-success {
  background: var(--success-500);
}
.app-timeline__dot.is-warning {
  background: var(--warning-500);
}
.app-timeline__dot.is-danger {
  background: var(--danger-500);
}
.app-timeline__dot.is-primary {
  background: var(--primary-600);
}
.app-timeline__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-timeline__title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.app-timeline__meta {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  flex-wrap: wrap;
}
.app-timeline__module {
  color: var(--primary-600);
}
.app-timeline__desc {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
}
</style>
