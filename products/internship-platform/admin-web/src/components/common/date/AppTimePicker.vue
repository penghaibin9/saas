<template>
  <div class="app-time" :class="{ 'is-disabled': disabled }">
    <label v-if="label" class="app-time__label">{{ label }}<i v-if="required">*</i></label>
    <input
      class="app-time__input"
      type="time"
      :value="modelValue || ''"
      :placeholder="placeholder"
      :disabled="disabled"
      :step="step"
      :aria-label="label || placeholder"
      @input="onInput"
      @change="$emit('change', $event.target.value)"
    />
  </div>
</template>

<script>
/** 统一时间选择器，值格式 HH:mm；业务页不得再要求用户手填 HH:MM。 */
export default {
  name: 'AppTimePicker',
  props: {
    modelValue: { type: String, default: '' },
    label: { type: String, default: '' },
    placeholder: { type: String, default: '请选择时间' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    step: { type: Number, default: 300 }
  },
  emits: ['update:modelValue', 'change'],
  methods: {
    onInput(event) { this.$emit('update:modelValue', event.target.value) }
  }
}
</script>

<style scoped>
.app-time { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-time__label { font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-secondary); }
.app-time__label i { color: var(--danger-600); font-style: normal; }
.app-time__input {
  width: 100%; height: 34px; box-sizing: border-box; padding: 0 var(--space-2);
  border: 1px solid var(--border-base); border-radius: var(--radius-base);
  background: var(--bg-card); color: var(--text-primary); font: inherit;
}
.app-time__input:focus { outline: none; border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.is-disabled .app-time__input { background: var(--bg-disabled); cursor: not-allowed; }
</style>
