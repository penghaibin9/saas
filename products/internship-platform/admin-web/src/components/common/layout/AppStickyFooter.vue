<template>
  <div class="app-sticky-footer" :class="[`is-${align}`, { 'is-raised': raised }]">
    <div v-if="$slots.info" class="app-sticky-footer__info">
      <slot name="info" />
    </div>
    <div class="app-sticky-footer__actions">
      <slot />
    </div>
  </div>
</template>

<script>
/**
 * AppStickyFooter — 表单/详情页底部吸底操作条（保存/取消常驻可见）。
 * Props:
 *  - align: right | between | center（default 插槽按钮的对齐）
 *  - raised: 是否显示上边阴影（内容可滚动时开）
 * Slots: info（左侧提示，如“共 3 处未保存”）/ default（右侧按钮）
 */
export default {
  name: 'AppStickyFooter',
  props: {
    align: {
      type: String,
      default: 'right',
      validator: (v) => ['right', 'between', 'center'].includes(v)
    },
    raised: { type: Boolean, default: true }
  }
}
</script>

<style scoped>
.app-sticky-footer {
  position: sticky;
  bottom: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-5);
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
}
.app-sticky-footer.is-raised {
  box-shadow: 0 -4px 12px rgba(15, 40, 90, 0.06);
}
.app-sticky-footer__info {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-sticky-footer__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}
.app-sticky-footer.is-between .app-sticky-footer__actions { margin-left: 0; }
.app-sticky-footer.is-between { justify-content: space-between; }
.app-sticky-footer.is-center .app-sticky-footer__actions { margin: 0 auto; }
</style>
