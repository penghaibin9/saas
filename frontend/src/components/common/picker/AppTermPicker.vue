<template>
  <AppSelect
    :model-value="modelValue"
    :options="termOptions"
    :placeholder="placeholder"
    :disabled="disabled"
    :size="size"
    :status="status"
    @update:model-value="$emit('update:modelValue', $event)"
    @change="$emit('change', $event)"
  />
</template>

<script>
/**
 * AppTermPicker — 学期选择器（默认「上学期 / 下学期」，可传 options 覆盖为「第1学期…」等口径）。
 * Props: modelValue / options / disabled / size / status
 * Emits: update:modelValue / change
 */
import AppSelect from '../form/AppSelect.vue'

const DEFAULT_TERMS = [
  { label: '上学期', value: '1' },
  { label: '下学期', value: '2' }
]

export default {
  name: 'AppTermPicker',
  components: { AppSelect },
  props: {
    modelValue: { type: [String, Number], default: '' },
    options: { type: Array, default: () => DEFAULT_TERMS },
    placeholder: { type: String, default: '请选择学期' },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'normal' },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    termOptions() { return this.options }
  }
}
</script>
