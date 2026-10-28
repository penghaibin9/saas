<template>
  <div class="tac">
    <button
      v-for="a in visibleActions"
      :key="a.key"
      type="button"
      class="tac__btn"
      :class="{ 'is-danger': a.danger, 'is-disabled': a.disabled }"
      :disabled="a.disabled"
      :title="a.disabled ? a.disabledReason || '当前角色无此操作权限' : ''"
      @click.stop="onClick(a)"
    >
      {{ a.label }}
    </button>
  </div>
</template>

<script>
/**
 * TableActionColumn — 表格操作列（模块局部组件，权限置灰/隐藏统一在此收口）。
 * Props: actions [{ key, label, danger?, disabled?, disabledReason?, visible? }]
 * Emits: action(key)
 */
export default {
  name: 'TableActionColumn',
  props: {
    actions: { type: Array, default: () => [] }
  },
  emits: ['action'],
  computed: {
    visibleActions() {
      return this.actions.filter((a) => a.visible !== false)
    }
  },
  methods: {
    onClick(a) {
      if (a.disabled) return
      this.$emit('action', a.key)
    }
  }
}
</script>

<style scoped>
.tac {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}
.tac__btn {
  border: none;
  background: none;
  padding: 2px var(--space-2);
  border-radius: var(--radius-base);
  font-size: var(--font-size-xs);
  color: var(--primary-600);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--motion-fast) var(--ease-standard);
}
.tac__btn:hover:not(:disabled) {
  background: var(--primary-50);
}
.tac__btn.is-danger {
  color: var(--danger-600);
}
.tac__btn.is-danger:hover:not(:disabled) {
  background: var(--danger-50);
}
.tac__btn.is-disabled,
.tac__btn:disabled {
  color: var(--text-disabled);
  cursor: not-allowed;
}
</style>
