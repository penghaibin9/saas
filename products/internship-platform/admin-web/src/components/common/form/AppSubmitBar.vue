<template>
  <div class="app-submit-bar" :class="[`is-${align}`, { 'is-sticky': sticky }]">
    <div v-if="$slots.info" class="app-submit-bar__info"><slot name="info" /></div>
    <div class="app-submit-bar__btns">
      <AppButton v-if="showReset" variant="ghost" :disabled="loading" @click="$emit('reset')">
        {{ resetText }}
      </AppButton>
      <AppButton v-if="showCancel" variant="secondary" :disabled="loading" @click="$emit('cancel')">
        {{ cancelText }}
      </AppButton>
      <AppButton
        :variant="danger ? 'danger' : 'primary'"
        :loading="loading"
        :disabled="disabled"
        @click="$emit('submit')"
      >{{ submitText }}</AppButton>
    </div>
  </div>
</template>

<script>
/**
 * AppSubmitBar — 表单提交条（提交 / 取消 / 重置，统一 loading 与禁用）。
 * 只负责按钮布局与状态；真实提交逻辑与后端校验由业务方在 @submit 内处理。
 * Props: submitText/cancelText/resetText / showCancel / showReset / loading / disabled / danger
 *   / sticky(吸底) / align(right|between|center)
 * Emits: submit / cancel / reset
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AppSubmitBar',
  components: { AppButton },
  props: {
    submitText: { type: String, default: '提交' },
    cancelText: { type: String, default: '取消' },
    resetText: { type: String, default: '重置' },
    showCancel: { type: Boolean, default: true },
    showReset: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    danger: { type: Boolean, default: false },
    sticky: { type: Boolean, default: false },
    align: { type: String, default: 'right', validator: (v) => ['right', 'between', 'center'].includes(v) }
  },
  emits: ['submit', 'cancel', 'reset']
}
</script>

<style scoped>
.app-submit-bar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) 0;
}
.app-submit-bar.is-sticky {
  position: sticky;
  bottom: 0;
  z-index: 10;
  padding: var(--space-3) var(--space-5);
  margin: 0 calc(-1 * var(--space-5)) calc(-1 * var(--space-5));
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  box-shadow: 0 -4px 12px rgba(15, 40, 90, 0.06);
}
.app-submit-bar__info { font-size: var(--font-size-sm); color: var(--text-secondary); }
.app-submit-bar__btns { display: flex; align-items: center; gap: var(--space-2); margin-left: auto; }
.app-submit-bar.is-between .app-submit-bar__btns { margin-left: 0; }
.app-submit-bar.is-between { justify-content: space-between; }
.app-submit-bar.is-center .app-submit-bar__btns { margin: 0 auto; }
</style>
