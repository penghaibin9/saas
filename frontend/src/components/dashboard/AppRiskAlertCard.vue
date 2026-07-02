<template>
  <div class="app-risk-alert-card" :class="`is-${level.toLowerCase()}`">
    <div class="app-risk-alert-card__main">
      <div class="app-risk-alert-card__title-row">
        <AppRiskTag :level="level" />
        <h3>{{ title }}</h3>
        <AppStatusTag :status="status" />
      </div>
      <p class="app-risk-alert-card__rule">{{ rule }}</p>
      <div class="app-risk-alert-card__meta">
        <span
          >涉及 <strong>{{ count }}</strong> 人</span
        >
        <span>责任人 {{ owner }}</span>
        <span>{{ statusLabel }}</span>
      </div>
    </div>
    <button type="button" class="app-risk-alert-card__btn" @click="$emit('handle')">去处理</button>
  </div>
</template>

<script>
import AppRiskTag from '../common/AppRiskTag.vue'
import AppStatusTag from '../common/AppStatusTag.vue'

export default {
  name: 'AppRiskAlertCard',
  components: { AppRiskTag, AppStatusTag },
  props: {
    title: { type: String, required: true },
    level: { type: String, default: 'MEDIUM' },
    rule: { type: String, required: true },
    count: { type: Number, default: 0 },
    owner: { type: String, default: '' },
    status: { type: String, default: 'PENDING_HANDLE' },
    statusLabel: { type: String, default: '' }
  },
  emits: ['handle']
}
</script>

<style scoped>
.app-risk-alert-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--card-border);
  border-left: 4px solid var(--warning-500);
  border-radius: var(--radius-card-sm);
  box-shadow: var(--shadow-card);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}
.app-risk-alert-card.is-high,
.app-risk-alert-card.is-critical {
  border-left-color: var(--danger-500);
  background: var(--danger-50);
}
.app-risk-alert-card.is-medium {
  border-left-color: var(--warning-500);
}
.app-risk-alert-card.is-low {
  border-left-color: var(--primary-600);
}
.app-risk-alert-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}
.app-risk-alert-card__main {
  flex: 1;
  min-width: 0;
}
.app-risk-alert-card__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-risk-alert-card__title-row h3 {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.app-risk-alert-card__rule {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}
.app-risk-alert-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.app-risk-alert-card__meta strong {
  color: var(--danger-600);
  font-weight: var(--font-weight-bold);
}
.app-risk-alert-card__btn {
  flex-shrink: 0;
  height: 36px;
  padding: 0 var(--space-4);
  border: 1px solid var(--primary-600);
  border-radius: var(--radius-md);
  background: var(--primary-600);
  color: var(--text-inverse);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s ease;
}
.app-risk-alert-card__btn:hover {
  background: var(--primary-700);
  border-color: var(--primary-700);
}
</style>
