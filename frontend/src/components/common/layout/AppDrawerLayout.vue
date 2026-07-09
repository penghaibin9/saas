<template>
  <div class="app-drawer-layout">
    <header class="app-drawer-layout__head">
      <div class="app-drawer-layout__titles">
        <h3 class="app-drawer-layout__title">{{ title }}</h3>
        <p v-if="subtitle" class="app-drawer-layout__subtitle">{{ subtitle }}</p>
      </div>
      <div class="app-drawer-layout__head-extra">
        <slot name="head-extra" />
        <button
          v-if="closable"
          type="button"
          class="app-drawer-layout__close"
          aria-label="关闭"
          @click="$emit('close')"
        >✕</button>
      </div>
    </header>

    <div class="app-drawer-layout__body">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="app-drawer-layout__footer">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script>
/**
 * AppDrawerLayout — 抽屉/弹窗内部标准布局（固定标题 + 可滚动内容 + 吸底页脚）。
 * 放进 ui/AppDrawer 里使用，统一详情/编辑抽屉的骨架。
 * Props: title / subtitle / closable
 * Slots: head-extra（标题右侧）/ default（内容，超出滚动）/ footer（底部操作）
 * Emits: close
 */
export default {
  name: 'AppDrawerLayout',
  props: {
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    closable: { type: Boolean, default: true }
  },
  emits: ['close']
}
</script>

<style scoped>
.app-drawer-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.app-drawer-layout__head {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.app-drawer-layout__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-drawer-layout__subtitle {
  margin: 2px 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-drawer-layout__head-extra {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
.app-drawer-layout__close {
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: var(--font-size-md);
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-base);
}
.app-drawer-layout__close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.app-drawer-layout__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-5);
}
.app-drawer-layout__footer {
  flex-shrink: 0;
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
  background: var(--bg-subtle);
}
</style>
