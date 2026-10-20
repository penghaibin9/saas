<template>
  <div
    class="app-text-input"
    :class="[`is-${size}`, { 'is-disabled': disabled, 'is-readonly': readonly, 'is-error': status === 'error', 'is-focus': focused }]"
  >
    <span v-if="$slots.prefix || prefixIcon" class="app-text-input__affix">
      <slot name="prefix">{{ prefixIcon }}</slot>
    </span>
    <input
      :id="id"
      ref="input"
      class="app-text-input__el"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :maxlength="maxlength > 0 ? maxlength : null"
      :aria-invalid="status === 'error'"
      @input="onInput"
      @change="$emit('change', $event.target.value)"
      @focus="onFocus"
      @blur="onBlur"
    />
    <button
      v-if="clearable && modelValue && !disabled && !readonly"
      type="button"
      class="app-text-input__clear"
      aria-label="清空"
      tabindex="-1"
      @click="onClear"
    >✕</button>
    <span v-if="$slots.suffix" class="app-text-input__affix"><slot name="suffix" /></span>
  </div>
</template>

<script>
/**
 * AppTextInput — 统一文本输入框（text/password/email/tel/search）。
 * v-model 绑定值。Props: type/placeholder/disabled/readonly/clearable/size(normal|compact)/
 *   status(default|error)/maxlength/prefixIcon。Slots: prefix / suffix。
 * Emits: update:modelValue / input / change / focus / blur / clear
 */
export default {
  name: 'AppTextInput',
  props: {
    modelValue: { type: [String, Number], default: '' },
    id: { type: String, default: '' },
    type: { type: String, default: 'text' },
    placeholder: { type: String, default: '请输入' },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    clearable: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    status: { type: String, default: 'default' },
    maxlength: { type: Number, default: 0 },
    prefixIcon: { type: String, default: '' }
  },
  emits: ['update:modelValue', 'input', 'change', 'focus', 'blur', 'clear'],
  data() {
    return { focused: false }
  },
  methods: {
    onInput(e) {
      this.$emit('update:modelValue', e.target.value)
      this.$emit('input', e.target.value)
    },
    onFocus(e) { this.focused = true; this.$emit('focus', e) },
    onBlur(e) { this.focused = false; this.$emit('blur', e) },
    onClear() {
      this.$emit('update:modelValue', '')
      this.$emit('clear')
      this.$refs.input && this.$refs.input.focus()
    }
  }
}
</script>

<style scoped>
.app-text-input {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  width: 100%;
  height: 34px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-text-input.is-compact { height: 28px; padding: 0 var(--space-2); }
.app-text-input.is-focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}
.app-text-input.is-error {
  border-color: var(--danger-500);
}
.app-text-input.is-error.is-focus {
  box-shadow: 0 0 0 3px var(--danger-100);
}
.app-text-input.is-disabled {
  background: var(--bg-disabled);
  cursor: not-allowed;
}
.app-text-input.is-readonly { background: var(--bg-subtle); }
.app-text-input__el {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--font-size-base);
  color: var(--text-primary);
  font-family: inherit;
}
.app-text-input.is-compact .app-text-input__el { font-size: var(--font-size-sm); }
.app-text-input__el::placeholder { color: var(--text-disabled); }
.app-text-input__el:disabled { cursor: not-allowed; }
.app-text-input__affix {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  display: inline-flex;
  align-items: center;
}
.app-text-input__clear {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 11px;
  padding: 0 2px;
}
.app-text-input__clear:hover { color: var(--text-secondary); }
</style>
