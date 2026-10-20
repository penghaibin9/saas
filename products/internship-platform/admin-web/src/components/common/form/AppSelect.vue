<template>
  <div
    class="app-select"
    :class="[`is-${size}`, { 'is-disabled': disabled, 'is-error': status === 'error', 'is-placeholder': isEmpty }]"
  >
    <select
      :id="id"
      class="app-select__el"
      :value="modelValue"
      :disabled="disabled"
      :aria-invalid="status === 'error'"
      @change="onChange"
    >
      <option v-if="placeholder" value="" disabled :selected="isEmpty">{{ placeholder }}</option>
      <option
        v-for="opt in normalizedOptions"
        :key="opt.value"
        :value="opt.value"
        :disabled="opt.disabled"
      >{{ opt.label }}</option>
    </select>
    <span class="app-select__chevron" aria-hidden="true">▾</span>
  </div>
</template>

<script>
/**
 * AppSelect — 统一单选下拉（基于原生 select，键盘/无障碍友好）。
 * v-model 绑定选中值。Props:
 *  - options: [{ label, value, disabled? }] 或 [{ [labelKey], [valueKey] }]
 *  - labelKey/valueKey: 自定义字段名
 *  - placeholder/disabled/size/status
 * Emits: update:modelValue / change
 * 远程搜索型请用 Group3 业务选择器（AppStudentPicker 等）。
 */
export default {
  name: 'AppSelect',
  props: {
    modelValue: { type: [String, Number], default: '' },
    id: { type: String, default: '' },
    options: { type: Array, default: () => [] },
    labelKey: { type: String, default: 'label' },
    valueKey: { type: String, default: 'value' },
    placeholder: { type: String, default: '请选择' },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (
        typeof o === 'object'
          ? { label: o[this.labelKey], value: o[this.valueKey], disabled: o.disabled }
          : { label: o, value: o }
      ))
    },
    isEmpty() {
      return this.modelValue === '' || this.modelValue === null || this.modelValue === undefined
    }
  },
  methods: {
    onChange(e) {
      this.$emit('update:modelValue', e.target.value)
      this.$emit('change', e.target.value)
    }
  }
}
</script>

<style scoped>
.app-select {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-select.is-compact { height: 28px; }
.app-select:focus-within { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.app-select.is-error { border-color: var(--danger-500); }
.app-select.is-disabled { background: var(--bg-disabled); }
.app-select__el {
  appearance: none;
  -webkit-appearance: none;
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  padding: 0 var(--space-5) 0 var(--space-3);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  font-family: inherit;
  cursor: pointer;
}
.app-select.is-compact .app-select__el { font-size: var(--font-size-sm); }
.app-select.is-placeholder .app-select__el { color: var(--text-disabled); }
.app-select__el:disabled { cursor: not-allowed; }
.app-select__chevron {
  position: absolute;
  right: var(--space-3);
  color: var(--text-tertiary);
  font-size: 10px;
  pointer-events: none;
}
</style>
