<template>
  <div class="atp">
    <div v-if="!logs.length" class="atp__empty">暂无操作留痕</div>
    <ol v-else class="atp__list">
      <li v-for="log in logs" :key="log.id" class="atp__item">
        <span class="atp__dot" />
        <div class="atp__main">
          <div class="atp__head">
            <span class="atp__action">{{ log.action }}</span>
            <span class="atp__time">{{ log.time }}</span>
          </div>
          <div class="atp__detail">{{ log.detail }}</div>
          <div class="atp__meta">
            {{ log.operator }}<template v-if="log.roleName">（{{ log.roleName }}）</template>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script>
/**
 * AuditTrailPanel — 操作留痕时间线（模块局部组件）。
 * Props: logs [{ id, time, operator, roleName?, action, detail }]（来自 mock/api auditTrail）
 */
export default {
  name: 'AuditTrailPanel',
  props: {
    logs: { type: Array, default: () => [] }
  }
}
</script>

<style scoped>
.atp__empty {
  padding: var(--space-6);
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.atp__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.atp__item {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) 0;
}
.atp__item + .atp__item {
  border-top: 1px dashed var(--border-light);
}
.atp__dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: var(--radius-full);
  background: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.atp__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}
.atp__action {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.atp__time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.atp__detail {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.atp__meta {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
