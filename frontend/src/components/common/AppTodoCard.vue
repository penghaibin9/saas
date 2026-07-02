<template>
  <div class="app-todo-card" :class="[`is-${priority || 'normal'}`, { 'is-overdue': overdue }]">
    <div class="app-todo-card__main">
      <div class="app-todo-card__title-row">
        <span class="app-todo-card__title">{{ title }}</span>
        <AppStatusTag v-if="status" :status="status" />
      </div>
      <div class="app-todo-card__meta">
        <span v-if="sourceModule" class="app-todo-card__module">{{ sourceModule }}</span>
        <span v-if="studentName" class="app-todo-card__student">{{ studentName }}</span>
        <span
          v-if="deadline"
          class="app-todo-card__deadline"
          :class="{ 'is-overdue-text': overdue }"
        >
          截止 {{ deadline }}
        </span>
        <span v-if="priorityLabel" class="app-todo-card__priority" :class="`is-${priority}`">
          {{ priorityLabel }}
        </span>
      </div>
    </div>
    <div class="app-todo-card__actions">
      <slot name="actions">
        <button type="button" class="app-todo-card__btn" @click="$emit('handle')">去处理</button>
      </slot>
    </div>
  </div>
</template>

<script>
import AppStatusTag from './AppStatusTag.vue'

export default {
  name: 'AppTodoCard',
  components: { AppStatusTag },
  props: {
    title: { type: String, required: true },
    sourceModule: { type: String, default: '' },
    studentName: { type: String, default: '' },
    deadline: { type: String, default: '' },
    priority: {
      type: String,
      default: '',
      validator: (v) => !v || ['high', 'medium', 'low'].includes(v)
    },
    status: { type: String, default: '' },
    overdue: { type: Boolean, default: false }
  },
  emits: ['handle'],
  computed: {
    priorityLabel() {
      return { high: '高优先级', medium: '中优先级', low: '普通' }[this.priority] || ''
    }
  }
}
</script>

<style scoped>
.app-todo-card {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card-sm);
  padding: var(--space-3) var(--space-4);
  box-shadow: var(--shadow-card);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}
.app-todo-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--primary-600);
}
.app-todo-card.is-high::before {
  background: var(--danger-500);
}
.app-todo-card.is-medium::before {
  background: var(--warning-500);
}
.app-todo-card.is-low::before,
.app-todo-card.is-normal::before {
  background: var(--primary-600);
}
.app-todo-card:hover {
  border-color: var(--primary-100);
  background: var(--primary-50);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.app-todo-card.is-overdue {
  border-color: var(--danger-100);
  background: var(--danger-50);
}
.app-todo-card.is-overdue:hover {
  background: var(--danger-50);
}
.app-todo-card__main {
  min-width: 0;
  flex: 1;
  padding-left: var(--space-1);
}
.app-todo-card__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-todo-card__title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-todo-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-todo-card__module {
  flex-basis: 100%;
  color: var(--primary-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}
.app-todo-card__deadline.is-overdue-text {
  color: var(--danger-600);
}
.app-todo-card__priority.is-high {
  color: var(--danger-600);
}
.app-todo-card__priority.is-medium {
  color: var(--warning-600);
}
.app-todo-card__priority.is-low {
  color: var(--text-tertiary);
}
.app-todo-card__actions {
  flex-shrink: 0;
  display: flex;
  gap: var(--space-2);
}
.app-todo-card__btn {
  height: 36px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--primary-600);
  background: var(--primary-600);
  color: var(--text-inverse);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}
.app-todo-card__btn:hover {
  background: var(--primary-700);
  border-color: var(--primary-700);
}
</style>
