<template>
  <dl
    class="app-desc-list"
    :class="[`is-${layout}`, `is-${size}`, { 'is-bordered': bordered }]"
    :style="{ '--app-desc-cols': columns }"
  >
    <div
      v-for="(it, i) in items"
      :key="it.key || it.label || i"
      class="app-desc-list__item"
      :style="it.span > 1 ? { 'grid-column': `span ${Math.min(it.span, columns)}` } : null"
    >
      <dt class="app-desc-list__label" :style="layout === 'horizontal' ? { width: labelWidth } : null">
        {{ it.label }}
      </dt>
      <dd class="app-desc-list__value">
        <slot :name="it.key" :item="it">
          <span :class="{ 'app-desc-list__empty': isEmpty(it.value) }">
            {{ isEmpty(it.value) ? emptyText : it.value }}
          </span>
        </slot>
      </dd>
    </div>
  </dl>
</template>

<script>
/**
 * AppDescriptionList — 详情键值展示（学生详情、审批详情、企业详情等）。
 * Props:
 *  - items: [{ key?, label, value, span? }]（span 跨列）
 *  - columns: 列数（默认 2，窄屏自动降为 1）
 *  - layout: horizontal(label 左) | vertical(label 上)
 *  - bordered / size(normal|compact) / labelWidth / emptyText
 * 具名插槽：以 item.key 命名，可放 AppSensitiveText / AppCopyableText / AppStatusTag 等。
 */
export default {
  name: 'AppDescriptionList',
  props: {
    items: { type: Array, default: () => [] },
    columns: { type: Number, default: 2 },
    layout: { type: String, default: 'horizontal', validator: (v) => ['horizontal', 'vertical'].includes(v) },
    bordered: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    labelWidth: { type: String, default: '96px' },
    emptyText: { type: String, default: '未设置' }
  },
  methods: {
    isEmpty(v) { return v === '' || v === null || v === undefined }
  }
}
</script>

<style scoped>
.app-desc-list {
  display: grid;
  grid-template-columns: repeat(var(--app-desc-cols, 2), minmax(0, 1fr));
  gap: 0;
  margin: 0;
}
.app-desc-list.is-bordered {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  overflow: hidden;
}
.app-desc-list__item {
  display: flex;
  min-width: 0;
  padding: var(--space-3) var(--space-4);
}
.is-compact .app-desc-list__item { padding: var(--space-2) var(--space-3); }
.is-vertical .app-desc-list__item { flex-direction: column; gap: 2px; }
.is-bordered .app-desc-list__item { border-bottom: 1px solid var(--border-light); border-right: 1px solid var(--border-light); }
.app-desc-list__label {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  margin: 0;
}
.is-horizontal .app-desc-list__label { padding-right: var(--space-3); }
.app-desc-list__value {
  flex: 1;
  min-width: 0;
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  word-break: break-word;
}
.app-desc-list__empty { color: var(--text-disabled); }
@media (max-width: 720px) {
  .app-desc-list { grid-template-columns: 1fr; }
}
</style>
