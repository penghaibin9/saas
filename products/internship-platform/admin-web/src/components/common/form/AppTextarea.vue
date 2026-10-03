<template>
  <div class="app-textarea" :class="{ 'is-error': status === 'error', 'is-focus': focused, 'is-disabled': disabled }">
    <textarea
      :id="id"
      ref="el"
      class="app-textarea__el"
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      :disabled="disabled"
      :readonly="readonly"
      :maxlength="maxlength > 0 ? maxlength : null"
      :aria-invalid="status === 'error'"
      @input="onInput"
      @focus="focused = true"
      @blur="onBlur"
    />
    <span v-if="showCount && maxlength > 0" class="app-textarea__count">
      {{ (modelValue || '').length }}/{{ maxlength }}
    </span>
  </div>
</template>

<script>
/**
 * AppTextarea — 多行文本输入。v-model 绑定字符串。
 * Props: rows/placeholder/disabled/readonly/maxlength/showCount(字数统计)/status。
 * Emits: update:modelValue / change / blur
 */
export default {
  name: 'AppTextarea',
  props: {
    modelValue: { type: String, default: '' },
    id: { type: String, default: '' },
    rows: { type: Number, default: 3 },
    placeholder: { type: String, default: '请输入' },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    maxlength: { type: Number, default: 0 },
    showCount: { type: Boolean, default: false },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change', 'blur'],
  data() {
    return { focused: false }
  },
  methods: {
    onInput(e) { this.$emit('update:modelValue', e.target.value) },
    onBlur(e) { this.focused = false; this.$emit('blur', e); this.$emit('change', e.target.value) }
  }
}
</script>

<style scoped>
.app-textarea {
  position: relative;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-textarea.is-focus { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.app-textarea.is-error { border-color: var(--danger-500); }
.app-textarea.is-disabled { background: var(--bg-disabled); }
.app-textarea__el {
  display: block;
  width: 100%;
  box-sizing: border-box;
  border: none;
  outline: none;
  background: transparent;
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  font-family: inherit;
  line-height: var(--line-height-base);
  resize: vertical;
}
.app-textarea__el::placeholder { color: var(--text-disabled); }
.app-textarea__count {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  background: var(--bg-card);
  padding-left: var(--space-1);
}
</style>
