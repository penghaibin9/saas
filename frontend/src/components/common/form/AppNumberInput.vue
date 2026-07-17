<template>
  <div
    class="app-number-input"
    :class="[`is-${size}`, { 'is-disabled': disabled, 'is-error': status === 'error', 'is-focus': focused }]"
  >
    <button
      v-if="controls"
      type="button"
      class="app-number-input__step"
      :disabled="disabled || readonly || atMin"
      aria-label="减少"
      tabindex="-1"
      @click="stepBy(-1)"
    >−</button>
    <input
      :id="id"
      ref="input"
      class="app-number-input__el"
      type="text"
      inputmode="decimal"
      :value="focused ? raw : displayValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :aria-invalid="status === 'error'"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
    />
    <button
      v-if="controls"
      type="button"
      class="app-number-input__step"
      :disabled="disabled || readonly || atMax"
      aria-label="增加"
      tabindex="-1"
      @click="stepBy(1)"
    >+</button>
  </div>
</template>

<script>
/**
 * AppNumberInput — 数字输入框（支持步进、最小/最大、精度）。
 * v-model 绑定 Number。Props: min/max/step/precision/controls(步进按钮)/disabled/readonly/size/status。
 * Emits: update:modelValue / change
 * 越界自动回夹到 [min,max]；空值回传 null。
 */
export default {
  name: 'AppNumberInput',
  props: {
    modelValue: { type: [Number, String], default: null },
    id: { type: String, default: '' },
    min: { type: Number, default: -Infinity },
    max: { type: Number, default: Infinity },
    step: { type: Number, default: 1 },
    precision: { type: Number, default: null },
    controls: { type: Boolean, default: true },
    placeholder: { type: String, default: '请输入' },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return { focused: false, raw: '' }
  },
  computed: {
    numValue() {
      const n = Number(this.modelValue)
      return this.modelValue === null || this.modelValue === '' || Number.isNaN(n) ? null : n
    },
    displayValue() {
      if (this.numValue === null) return ''
      if (this.precision != null) return this.numValue.toFixed(this.precision)
      return String(this.numValue)
    },
    atMin() { return this.numValue != null && this.numValue <= this.min },
    atMax() { return this.numValue != null && this.numValue >= this.max }
  },
  methods: {
    clamp(n) {
      let v = Math.min(this.max, Math.max(this.min, n))
      if (this.precision != null) v = Number(v.toFixed(this.precision))
      return v
    },
    onFocus() {
      // 进入编辑态：用未格式化的当前值初始化本地输入串，避免 toFixed 补零挡住小数录入
      this.raw = this.numValue === null ? '' : String(this.numValue)
      this.focused = true
    },
    onInput(e) {
      this.raw = e.target.value
      const raw = e.target.value.trim()
      if (raw === '' || raw === '-') {
        this.$emit('update:modelValue', null)
        return
      }
      const n = Number(raw)
      if (Number.isNaN(n)) return
      this.$emit('update:modelValue', n)
    },
    onBlur() {
      this.focused = false
      if (this.numValue === null) { this.$emit('change', null); return }
      const clamped = this.clamp(this.numValue)
      if (clamped !== this.numValue) this.$emit('update:modelValue', clamped)
      this.$emit('change', clamped)
    },
    stepBy(dir) {
      const base = this.numValue == null ? 0 : this.numValue
      const next = this.clamp(base + dir * this.step)
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    }
  }
}
</script>

<style scoped>
.app-number-input {
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-number-input.is-compact { height: 28px; }
.app-number-input.is-focus { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.app-number-input.is-error { border-color: var(--danger-500); }
.app-number-input.is-disabled { background: var(--bg-disabled); cursor: not-allowed; }
.app-number-input__el {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  text-align: center;
  font-size: var(--font-size-base);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  font-family: inherit;
}
.app-number-input__el:disabled { cursor: not-allowed; }
.app-number-input__step {
  flex-shrink: 0;
  width: 32px;
  align-self: stretch;
  border: none;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-md);
  cursor: pointer;
}
.app-number-input__step:hover:not(:disabled) { background: var(--primary-50); color: var(--primary-600); }
.app-number-input__step:disabled { color: var(--text-disabled); cursor: not-allowed; }
</style>
