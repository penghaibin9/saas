<template>
  <div class="app-lifecycle-stage-card">
    <div class="app-lifecycle-stage-card__head">
      <h3>{{ name }}</h3>
      <AppStatusTag :type="statusType" :label="status" />
    </div>
    <div class="app-lifecycle-stage-card__rate">
      <span class="app-lifecycle-stage-card__value">{{ displayRate }}</span>
      <span v-if="rate != null" class="app-lifecycle-stage-card__unit">%</span>
    </div>
    <div class="app-lifecycle-stage-card__progress">
      <div
        class="app-lifecycle-stage-card__bar"
        :style="{ width: `${rate == null ? 0 : Math.min(rate, 100)}%` }"
      />
    </div>
    <div class="app-lifecycle-stage-card__footer">
      <span v-if="riskCount > 0" class="app-lifecycle-stage-card__risk"
        >风险 {{ riskCount }} 项</span
      >
      <span v-else class="app-lifecycle-stage-card__safe">运行正常</span>
      <button type="button" class="app-lifecycle-stage-card__action" @click="$emit('action')">
        {{ actionLabel }}
      </button>
    </div>
  </div>
</template>

<script>
import AppStatusTag from '../common/AppStatusTag.vue'

export default {
  name: 'AppLifecycleStageCard',
  components: { AppStatusTag },
  props: {
    name: { type: String, required: true },
    status: { type: String, required: true },
    statusType: { type: String, default: 'processing' },
    rate: { type: Number, default: null },
    riskCount: { type: Number, default: 0 },
    actionLabel: { type: String, default: '查看' }
  },
  emits: ['action'],
  computed: {
    displayRate() {
      return this.rate == null ? '--' : this.rate
    }
  }
}
</script>

<style scoped>
.app-lifecycle-stage-card {
  background: var(--bg-card);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card-sm);
  padding: var(--space-4);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  transition:
    transform var(--motion-normal) var(--ease-standard),
    box-shadow var(--motion-normal) var(--ease-standard);
  min-width: 0;
}
.app-lifecycle-stage-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}
.app-lifecycle-stage-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.app-lifecycle-stage-card__head h3 {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-lifecycle-stage-card__rate {
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.app-lifecycle-stage-card__value {
  font-size: 28px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: var(--font-numeric);
}
.app-lifecycle-stage-card__unit {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-lifecycle-stage-card__progress {
  height: 4px;
  background: var(--border-light);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.app-lifecycle-stage-card__bar {
  height: 100%;
  background: var(--primary-600);
  border-radius: var(--radius-full);
  transition: width var(--motion-slow) var(--ease-standard);
}
.app-lifecycle-stage-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: auto;
  font-size: var(--font-size-xs);
}
.app-lifecycle-stage-card__risk {
  color: var(--danger-500);
  font-weight: var(--font-weight-medium);
}
.app-lifecycle-stage-card__safe {
  color: var(--success-600);
}
.app-lifecycle-stage-card__action {
  height: 28px;
  padding: 0 var(--space-2);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--motion-normal) var(--ease-standard);
}
.app-lifecycle-stage-card__action:hover {
  background: var(--primary-100);
}
</style>
