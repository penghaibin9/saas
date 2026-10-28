<template>
  <div
    class="app-radio-group"
    :class="[`is-${variant}`, `is-${size}`, { 'is-block': block }]"
    role="radiogroup"
  >
    <label
      v-for="opt in normalizedOptions"
      :key="opt.value"
      class="app-radio"
      :class="{ 'is-checked': modelValue === opt.value, 'is-disabled': disabled || opt.disabled }"
    >
      <input
        type="radio"
        class="app-radio__input"
        :checked="modelValue === opt.value"
        :disabled="disabled || opt.disabled"
        @change="select(opt)"
      />
      <span v-if="variant === 'dot'" class="app-radio__dot" aria-hidden="true" />
      <span class="app-radio__label">{{ opt.label }}</span>
    </label>
  </div>
</template>

<script>
/**
 * AppRadioGroup — 单选组（dot 圆点样式 / button 按钮样式）。
 * v-model 绑定选中值。Props:
 *  - options: [{ label, value, disabled? }]
 *  - variant: dot | button
 *  - size: normal | compact；block: 每项占一行
 * Emits: update:modelValue / change
 */
export default {
  name: 'AppRadioGroup',
  props: {
    modelValue: { type: [String, Number, Boolean], default: '' },
    options: { type: Array, default: () => [] },
    variant: { type: String, default: 'dot', validator: (v) => ['dot', 'button'].includes(v) },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    disabled: { type: Boolean, default: false },
    block: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (
        typeof o === 'object' ? o : { label: o, value: o }
      ))
    }
  },
  methods: {
    select(opt) {
      if (this.disabled || opt.disabled) return
      this.$emit('update:modelValue', opt.value)
      this.$emit('change', opt.value)
    }
  }
}
</script>

<style scoped>
.app-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}
.app-radio-group.is-block { flex-direction: column; gap: var(--space-2); }
.app-radio {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: var(--font-size-base);
  color: var(--text-primary);
}
.is-compact .app-radio { font-size: var(--font-size-sm); }
.app-radio.is-disabled { cursor: not-allowed; color: var(--text-disabled); }
.app-radio__input { position: absolute; opacity: 0; width: 0; height: 0; }
.app-radio__dot {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--border-dark);
  border-radius: var(--radius-full);
  position: relative;
  flex-shrink: 0;
  transition: border-color 0.15s;
}
.app-radio.is-checked .app-radio__dot { border-color: var(--primary-600); }
.app-radio.is-checked .app-radio__dot::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: var(--radius-full);
  background: var(--primary-600);
}
.app-radio__input:focus-visible + .app-radio__dot {
  box-shadow: 0 0 0 3px var(--primary-100);
}
/* button 变体 */
.is-button { gap: 0; }
.is-button .app-radio {
  padding: 0 var(--space-4);
  height: 32px;
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  margin-left: -1px;
}
.is-button .app-radio:first-child { border-radius: var(--radius-base) 0 0 var(--radius-base); margin-left: 0; }
.is-button .app-radio:last-child { border-radius: 0 var(--radius-base) var(--radius-base) 0; }
.is-button.is-compact .app-radio { height: 28px; padding: 0 var(--space-3); }
.is-button .app-radio.is-checked {
  background: var(--primary-50);
  border-color: var(--primary-500);
  color: var(--primary-700);
  z-index: 1;
}
</style>
