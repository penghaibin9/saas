<template>
  <div class="app-process-record-row" :class="{ 'is-closed': closed }">
    <span class="app-process-record-row__time">{{ time }}</span>
    <span class="app-process-record-row__operator">{{ operator }}</span>
    <span class="app-process-record-row__action">{{ action }}</span>
    <span class="app-process-record-row__result">{{ result }}</span>
    <span class="app-process-record-row__status">
      <AppStatusTag
        :type="closed ? 'success' : 'warning'"
        :label="closed ? '已闭环' : '处理中'"
        dot
      />
    </span>
  </div>
</template>

<script>
import AppStatusTag from '../common/AppStatusTag.vue'

export default {
  name: 'AppProcessRecordRow',
  components: { AppStatusTag },
  props: {
    time: { type: String, required: true },
    operator: { type: String, required: true },
    action: { type: String, required: true },
    result: { type: String, required: true },
    closed: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.app-process-record-row {
  display: grid;
  grid-template-columns: 130px 80px 1fr 120px 90px;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  font-size: var(--font-size-sm);
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}
.app-process-record-row:hover {
  border-color: var(--primary-100);
  background: var(--primary-50);
}
.app-process-record-row__time {
  color: var(--text-tertiary);
  font-variant-numeric: var(--font-numeric);
  white-space: nowrap;
}
.app-process-record-row__operator {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}
.app-process-record-row__action {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-process-record-row__result {
  color: var(--text-secondary);
}
.app-process-record-row.is-closed .app-process-record-row__result {
  color: var(--success-600);
}
@media (max-width: 1200px) {
  .app-process-record-row {
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }
  .app-process-record-row__status {
    grid-column: 2;
    justify-self: end;
  }
}
</style>
