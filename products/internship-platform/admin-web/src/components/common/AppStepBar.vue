<template>
  <ol class="app-step-bar">
    <li
      v-for="(step, i) in steps"
      :key="step.key || i"
      class="app-step-bar__item"
      :class="stepClass(i)"
    >
      <span class="app-step-bar__index">
        <template v-if="statusOf(i) === 'done'">✓</template>
        <template v-else>{{ i + 1 }}</template>
      </span>
      <span class="app-step-bar__label">
        <span class="app-step-bar__title">{{ step.title }}</span>
        <span v-if="step.description" class="app-step-bar__desc">{{ step.description }}</span>
      </span>
      <span v-if="i < steps.length - 1" class="app-step-bar__line" />
    </li>
  </ol>
</template>

<script>
/**
 * AppStepBar 步骤条（流程节点：开题→中期→成果→答辩 等由业务方传入，本组件不写死）
 * Props:
 *  - steps: [{ key?, title, description?, status? ('done'|'active'|'wait'|'error') }]
 *  - current: 当前步骤下标（step.status 未指定时按 current 推断）
 */
export default {
  name: 'AppStepBar',
  props: {
    steps: { type: Array, required: true },
    current: { type: Number, default: 0 }
  },
  methods: {
    statusOf(i) {
      const s = this.steps[i] && this.steps[i].status
      if (s) return s
      if (i < this.current) return 'done'
      if (i === this.current) return 'active'
      return 'wait'
    },
    stepClass(i) {
      return `is-${this.statusOf(i)}`
    }
  }
}
</script>

<style scoped>
.app-step-bar {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
}
.app-step-bar__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
  position: relative;
}
.app-step-bar__index {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dark);
  background: var(--bg-card);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.is-done .app-step-bar__index {
  background: var(--success-500);
  border-color: var(--success-500);
  color: var(--text-inverse);
}
.is-active .app-step-bar__index {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: var(--text-inverse);
}
.is-error .app-step-bar__index {
  background: var(--danger-600);
  border-color: var(--danger-600);
  color: var(--text-inverse);
}
.app-step-bar__label {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.app-step-bar__title {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
}
.is-active .app-step-bar__title {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}
.is-error .app-step-bar__title {
  color: var(--danger-600);
}
.app-step-bar__desc {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}
.app-step-bar__line {
  flex: 1;
  height: 1px;
  background: var(--border-base);
  margin: 13px var(--space-2) 0;
}
.is-done .app-step-bar__line {
  background: var(--success-500);
}
</style>
