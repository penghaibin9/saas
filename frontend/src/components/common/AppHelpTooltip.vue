<template>
  <span class="app-help" :class="`is-${placement}`" tabindex="0">
    <span class="app-help__icon">{{ icon }}</span>
    <span class="app-help__bubble" role="tooltip">
      <slot>{{ content }}</slot>
    </span>
  </span>
</template>

<script>
/**
 * AppHelpTooltip — 字段/指标口径帮助气泡（悬停或聚焦显示）。
 * Props: content(纯文本，也可用默认插槽放富文本)、icon、placement: top|bottom
 * 纯展示，不承载业务逻辑；口径解释、填写说明用它统一呈现。
 */
export default {
  name: 'AppHelpTooltip',
  props: {
    content: { type: String, default: '' },
    icon: { type: String, default: '?' },
    placement: {
      type: String,
      default: 'top',
      validator: (v) => ['top', 'bottom'].includes(v)
    }
  }
}
</script>

<style scoped>
.app-help {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--text-tertiary);
  cursor: help;
  outline: none;
}
.app-help__icon {
  font-size: 11px;
  line-height: 1;
}
.app-help__bubble {
  position: absolute;
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  z-index: 30;
  min-width: 160px;
  max-width: 260px;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-800);
  color: var(--text-inverse);
  font-size: var(--font-size-xs);
  line-height: 1.5;
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-md);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.15s, transform 0.15s;
  white-space: normal;
  text-align: left;
  pointer-events: none;
}
.app-help.is-top .app-help__bubble { bottom: calc(100% + 6px); }
.app-help.is-bottom .app-help__bubble { top: calc(100% + 6px); }
.app-help:hover .app-help__bubble,
.app-help:focus .app-help__bubble {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}
</style>
