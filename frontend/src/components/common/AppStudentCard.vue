<template>
  <div class="app-student-card" :class="`is-${normalizedRisk}`" @click="$emit('view')">
    <div class="app-student-card__avatar">{{ avatarText }}</div>
    <div class="app-student-card__body">
      <div class="app-student-card__name-row">
        <span class="app-student-card__name">{{ name }}</span>
        <span v-if="studentNo" class="app-student-card__no">{{ studentNo }}</span>
        <AppRiskTag v-if="riskLevel" :level="riskLevel" />
      </div>
      <div v-if="orgText" class="app-student-card__org">{{ orgText }}</div>
      <div v-if="stage" class="app-student-card__stage">{{ stage }}</div>
      <div v-if="lastActivity" class="app-student-card__risk-block">
        <span class="app-student-card__risk-icon" aria-hidden="true">⚠</span>
        <span class="app-student-card__risk-text">{{ lastActivity }}</span>
      </div>
    </div>
    <div class="app-student-card__actions" @click.stop>
      <slot name="actions" />
    </div>
  </div>
</template>

<script>
import AppRiskTag from './AppRiskTag.vue'

export default {
  name: 'AppStudentCard',
  components: { AppRiskTag },
  props: {
    name: { type: String, required: true },
    studentNo: { type: String, default: '' },
    college: { type: String, default: '' },
    major: { type: String, default: '' },
    className: { type: String, default: '' },
    stage: { type: String, default: '' },
    riskLevel: { type: String, default: '' },
    lastActivity: { type: String, default: '' }
  },
  emits: ['view'],
  computed: {
    normalizedRisk() {
      return String(this.riskLevel || 'LOW').toUpperCase()
    },
    avatarText() {
      return this.name ? this.name.slice(0, 1) : '生'
    },
    orgText() {
      return [this.college, this.major, this.className].filter(Boolean).join(' · ')
    }
  }
}
</script>

<style scoped>
.app-student-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-card-sm);
  padding: var(--space-4);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}
.app-student-card.is-HIGH,
.app-student-card.is-CRITICAL {
  border-color: var(--danger-100);
}
.app-student-card:hover {
  border-color: var(--primary-100);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.app-student-card__avatar {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
  background: var(--danger-50);
  color: var(--danger-600);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  justify-content: center;
}
.app-student-card__body {
  flex: 1;
  min-width: 0;
}
.app-student-card__name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-student-card__name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.app-student-card__no {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  font-variant-numeric: var(--font-numeric);
}
.app-student-card__org {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}
.app-student-card__stage {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--primary-600);
  font-weight: var(--font-weight-medium);
}
.app-student-card__risk-block {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
}
.app-student-card__risk-icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1.4;
  color: var(--danger-500);
}
.app-student-card__risk-text {
  font-size: var(--font-size-sm);
  color: var(--danger-700);
  line-height: 1.5;
}
.app-student-card__actions {
  flex-shrink: 0;
  display: flex;
  gap: var(--space-2);
}
</style>
