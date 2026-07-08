<template>
  <div class="app-todo-panel">
    <div v-if="title || $slots.header" class="app-todo-panel__head">
      <span class="app-todo-panel__title">{{ title }}</span>
      <span v-if="items.length" class="app-todo-panel__count">{{ items.length }}</span>
      <slot name="header" />
    </div>

    <div v-if="loading" class="app-todo-panel__state"><span class="app-todo-panel__spinner" /> 加载待办…</div>
    <div v-else-if="!items.length" class="app-todo-panel__empty">
      <span class="app-todo-panel__empty-ico">✓</span>
      {{ emptyText }}
    </div>

    <ul v-else class="app-todo-panel__list">
      <li
        v-for="(t, i) in items"
        :key="t.id || i"
        class="app-todo-panel__item"
        :class="{ 'is-clickable': clickable }"
        @click="clickable && $emit('open', t)"
      >
        <span class="app-todo-panel__bar" :class="`is-${t.priority || 'normal'}`" />
        <div class="app-todo-panel__body">
          <div class="app-todo-panel__item-title">
            {{ t.title }}
            <span v-if="t.tag" class="app-todo-panel__tag">{{ t.tag }}</span>
          </div>
          <div v-if="t.meta || t.at" class="app-todo-panel__item-meta">
            <template v-if="t.meta">{{ t.meta }}</template>
            <template v-if="t.at"> · {{ t.at }}</template>
            <template v-if="t.overdue"> · <span class="app-todo-panel__overdue">已逾期</span></template>
          </div>
        </div>
        <button
          v-if="t.actionText"
          type="button"
          class="app-todo-panel__action"
          @click.stop="$emit('action', t)"
        >{{ t.actionText }}</button>
        <span v-else-if="clickable" class="app-todo-panel__arrow">›</span>
      </li>
    </ul>

    <button v-if="showMore && items.length" type="button" class="app-todo-panel__more" @click="$emit('more')">
      查看全部 ›
    </button>
  </div>
</template>

<script>
/**
 * AppTodoPanel — 工作台“我的待办”列表面板。
 * Props:
 *  - title、items: [{ id, title, meta?, at?, tag?, priority?(high|normal|low), overdue?, actionText? }]
 *  - loading、emptyText、clickable、showMore
 * Emits: open(item)、action(item)、more
 * 数据来自后端统一待办(UnifiedTodo)；本组件只渲染与派发。
 */
export default {
  name: 'AppTodoPanel',
  props: {
    title: { type: String, default: '我的待办' },
    items: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    emptyText: { type: String, default: '暂无待办，工作已处理完毕' },
    clickable: { type: Boolean, default: true },
    showMore: { type: Boolean, default: false }
  },
  emits: ['open', 'action', 'more']
}
</script>

<style scoped>
.app-todo-panel {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  overflow: hidden;
}
.app-todo-panel__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}
.app-todo-panel__title { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.app-todo-panel__count {
  min-width: 20px; height: 20px; padding: 0 var(--space-1);
  border-radius: var(--radius-full);
  background: var(--danger-500); color: #fff;
  font-size: var(--font-size-xs);
  display: inline-flex; align-items: center; justify-content: center;
}
.app-todo-panel__state, .app-todo-panel__empty {
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  font-size: var(--font-size-sm); color: var(--text-tertiary);
}
.app-todo-panel__empty-ico {
  width: 20px; height: 20px; border-radius: var(--radius-full);
  background: var(--success-50); color: var(--success-600);
  display: inline-flex; align-items: center; justify-content: center; font-size: var(--font-size-xs);
}
.app-todo-panel__spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--primary-100); border-top-color: var(--primary-500);
  border-radius: var(--radius-full); animation: atp-spin 0.7s linear infinite;
}
@keyframes atp-spin { to { transform: rotate(360deg); } }
.app-todo-panel__list { list-style: none; margin: 0; padding: 0; }
.app-todo-panel__item {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}
.app-todo-panel__item:last-child { border-bottom: none; }
.app-todo-panel__item.is-clickable { cursor: pointer; transition: background 0.12s; }
.app-todo-panel__item.is-clickable:hover { background: var(--bg-hover); }
.app-todo-panel__bar { width: 3px; align-self: stretch; border-radius: var(--radius-full); background: var(--gray-300); flex-shrink: 0; }
.app-todo-panel__bar.is-high { background: var(--danger-500); }
.app-todo-panel__bar.is-low { background: var(--gray-200); }
.app-todo-panel__body { flex: 1; min-width: 0; }
.app-todo-panel__item-title {
  font-size: var(--font-size-sm); color: var(--text-primary);
  display: flex; align-items: center; gap: var(--space-2);
}
.app-todo-panel__tag {
  font-size: var(--font-size-xs); padding: 0 var(--space-2);
  border-radius: var(--radius-full); background: var(--primary-50); color: var(--primary-700);
}
.app-todo-panel__item-meta { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.app-todo-panel__overdue { color: var(--danger-600); }
.app-todo-panel__action {
  flex-shrink: 0; border: 1px solid var(--primary-100);
  background: var(--primary-50); color: var(--primary-700);
  height: 28px; padding: 0 var(--space-3); border-radius: var(--radius-base);
  font-size: var(--font-size-xs); cursor: pointer;
}
.app-todo-panel__action:hover { background: var(--primary-100); }
.app-todo-panel__arrow { color: var(--text-tertiary); font-size: var(--font-size-lg); flex-shrink: 0; }
.app-todo-panel__more {
  width: 100%; border: none; background: var(--bg-subtle);
  padding: var(--space-2); color: var(--text-link); cursor: pointer;
  font-size: var(--font-size-sm);
}
.app-todo-panel__more:hover { background: var(--bg-hover); }
</style>
