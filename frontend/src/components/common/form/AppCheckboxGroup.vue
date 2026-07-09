<template>
  <div class="app-checkbox-group" :class="[`is-${size}`, { 'is-block': block }]">
    <label
      v-for="opt in normalizedOptions"
      :key="opt.value"
      class="app-checkbox"
      :class="{ 'is-checked': isChecked(opt.value), 'is-disabled': disabled || opt.disabled || isMaxed(opt.value) }"
    >
      <input
        type="checkbox"
        class="app-checkbox__input"
        :checked="isChecked(opt.value)"
        :disabled="disabled || opt.disabled || isMaxed(opt.value)"
        @change="toggle(opt)"
      />
      <span class="app-checkbox__box" aria-hidden="true">
        <span v-if="isChecked(opt.value)" class="app-checkbox__tick">✓</span>
      </span>
      <span class="app-checkbox__label">{{ opt.label }}</span>
    </label>
  </div>
</template>

<script>
/**
 * AppCheckboxGroup — 多选组。v-model 绑定数组。
 * Props: options:[{label,value,disabled?}] / max(最多选几个) / size / block(每项一行) / disabled
 * Emits: update:modelValue / change
 */
export default {
  name: 'AppCheckboxGroup',
  props: {
    modelValue: { type: Array, default: () => [] },
    options: { type: Array, default: () => [] },
    max: { type: Number, default: 0 },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    disabled: { type: Boolean, default: false },
    block: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
    }
  },
  methods: {
    isChecked(v) { return this.modelValue.includes(v) },
    isMaxed(v) {
      return this.max > 0 && this.modelValue.length >= this.max && !this.isChecked(v)
    },
    toggle(opt) {
      if (this.disabled || opt.disabled) return
      let next
      if (this.isChecked(opt.value)) {
        next = this.modelValue.filter((v) => v !== opt.value)
      } else {
        if (this.isMaxed(opt.value)) return
        next = [...this.modelValue, opt.value]
      }
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    }
  }
}
</script>

<style scoped>
.app-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}
.app-checkbox-group.is-block { flex-direction: column; gap: var(--space-2); }
.app-checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: var(--font-size-base);
  color: var(--text-primary);
}
.is-compact .app-checkbox { font-size: var(--font-size-sm); }
.app-checkbox.is-disabled { cursor: not-allowed; color: var(--text-disabled); }
.app-checkbox__input { position: absolute; opacity: 0; width: 0; height: 0; }
.app-checkbox__box {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--border-dark);
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}
.app-checkbox.is-checked .app-checkbox__box {
  background: var(--primary-600);
  border-color: var(--primary-600);
}
.app-checkbox__tick { color: #fff; font-size: 11px; line-height: 1; }
.app-checkbox__input:focus-visible + .app-checkbox__box { box-shadow: 0 0 0 3px var(--primary-100); }
</style>
