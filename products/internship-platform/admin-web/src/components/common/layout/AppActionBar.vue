<template>
  <div class="app-action-bar" :class="[`is-${align}`, { 'is-wrap': wrap }]">
    <div v-if="$slots.left" class="app-action-bar__group">
      <slot name="left" />
    </div>
    <div v-if="$slots.left && ($slots.default || $slots.right)" class="app-action-bar__spacer" />
    <div class="app-action-bar__group">
      <slot />
      <slot name="right" />
    </div>
  </div>
</template>

<script>
/**
 * AppActionBar — 操作按钮行（表单底部、卡片头部、抽屉底部通用）。
 * 只负责按钮排布与对齐，不含业务；按钮请用 AppButton / AppPermissionButton。
 * Props:
 *  - align: left | right | center | between（default/right 插槽的对齐）
 *  - wrap:  窄屏是否换行
 * Slots: left（左侧组）/ default + right（主操作组）
 */
export default {
  name: 'AppActionBar',
  props: {
    align: {
      type: String,
      default: 'right',
      validator: (v) => ['left', 'right', 'center', 'between'].includes(v)
    },
    wrap: { type: Boolean, default: true }
  }
}
</script>

<style scoped>
.app-action-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-action-bar.is-wrap {
  flex-wrap: wrap;
}
.app-action-bar__group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-action-bar__spacer {
  flex: 1;
}
.app-action-bar.is-left { justify-content: flex-start; }
.app-action-bar.is-right { justify-content: flex-end; }
.app-action-bar.is-center { justify-content: center; }
.app-action-bar.is-between { justify-content: space-between; }
</style>
