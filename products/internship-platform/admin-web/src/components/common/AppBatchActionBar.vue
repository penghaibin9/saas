<template>
  <transition name="abab-slide">
    <div v-if="count > 0" class="app-batch-bar" :class="{ 'is-float': float }">
      <div class="app-batch-bar__left">
        <span class="app-batch-bar__count">
          已选 <strong>{{ count }}</strong> 项<template v-if="total"> / 共 {{ total }} 项</template>
        </span>
        <button
          v-if="selectableAll"
          type="button"
          class="app-batch-bar__link"
          @click="$emit('select-all')"
        >{{ count >= total && total ? '取消全选' : '选择全部' }}</button>
        <button type="button" class="app-batch-bar__link" @click="$emit('clear')">清空</button>
      </div>
      <div class="app-batch-bar__actions">
        <button
          v-for="a in actions"
          :key="a.key"
          type="button"
          class="app-batch-bar__btn"
          :class="{ 'is-danger': a.danger, 'is-loading': loadingKey === a.key }"
          :disabled="a.disabled || (loadingKey && loadingKey !== a.key)"
          :title="a.disabledReason && a.disabled ? a.disabledReason : ''"
          @click="onAction(a)"
        >
          <span v-if="loadingKey === a.key" class="app-batch-bar__spinner" />
          <span v-else-if="a.icon" class="app-batch-bar__ico">{{ a.icon }}</span>
          {{ a.label }}
        </button>
      </div>
    </div>
  </transition>
</template>

<script>
/**
 * AppBatchActionBar — 批量操作条（列表多选后浮出）。
 *
 * Props:
 *  - count: 已选数量（>0 才显示）
 *  - total: 总数（可选，用于“x/共 y”与全选切换）
 *  - actions: [{ key, label, danger?, disabled?, disabledReason?, icon? }]
 *  - loadingKey: 正在执行的 action.key（该按钮转圈、其余禁用）
 *  - selectableAll / float
 * Emits: action(actionObj) / clear / select-all
 *
 * 批量导出/批量删除等高危动作，调用方仍需走确认框(AppConfirmDialog)+后端权限+审计。
 */
export default {
  name: 'AppBatchActionBar',
  props: {
    count: { type: Number, default: 0 },
    total: { type: Number, default: 0 },
    actions: { type: Array, default: () => [] },
    loadingKey: { type: String, default: '' },
    selectableAll: { type: Boolean, default: true },
    float: { type: Boolean, default: true }
  },
  emits: ['action', 'clear', 'select-all'],
  methods: {
    onAction(a) {
      if (a.disabled || this.loadingKey) return
      this.$emit('action', a)
    }
  }
}
</script>

<style scoped>
.app-batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-batchbar, var(--primary-700));
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}
.app-batch-bar.is-float {
  position: sticky;
  bottom: var(--space-4);
  z-index: 20;
  margin: var(--space-3) auto 0;
}
.app-batch-bar__left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
}
.app-batch-bar__count strong { font-size: var(--font-size-md); }
.app-batch-bar__link {
  border: none;
  background: none;
  color: var(--text-inverse);
  opacity: 0.8;
  cursor: pointer;
  font-size: var(--font-size-sm);
  text-decoration: underline;
}
.app-batch-bar__link:hover { opacity: 1; }
.app-batch-bar__actions { display: flex; gap: var(--space-2); }
.app-batch-bar__btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: var(--radius-base);
  background: rgba(255, 255, 255, 0.12);
  color: var(--text-inverse);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: background 0.15s;
}
.app-batch-bar__btn:hover:not(:disabled) { background: rgba(255, 255, 255, 0.24); }
.app-batch-bar__btn.is-danger {
  background: var(--danger-500);
  border-color: var(--danger-500);
}
.app-batch-bar__btn.is-danger:hover:not(:disabled) { background: var(--danger-600); }
.app-batch-bar__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.app-batch-bar__spinner {
  width: 12px; height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: var(--radius-full);
  animation: abab-spin 0.7s linear infinite;
}
@keyframes abab-spin { to { transform: rotate(360deg); } }
.abab-slide-enter-active, .abab-slide-leave-active { transition: all 0.2s ease; }
.abab-slide-enter-from, .abab-slide-leave-to { opacity: 0; transform: translateY(8px); }
</style>
