<template>
  <AppSelect
    :model-value="modelValue"
    :options="yearOptions"
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
 * AppAcademicYearPicker — 学年选择器（如「2025-2026 学年」）。
 * 默认按当前年份生成近 span 学年；也可传 options 覆盖。
 * Props: modelValue / span(生成几个学年,默认6) / forward(向后几年,默认1) / options / disabled / size / status
 * Emits: update:modelValue / change
 * 值形如 '2025-2026'。
 */
import AppSelect from '../form/AppSelect.vue'

export default {
  name: 'AppAcademicYearPicker',
  components: { AppSelect },
  props: {
    modelValue: { type: String, default: '' },
    span: { type: Number, default: 6 },
    forward: { type: Number, default: 1 },
    options: { type: Array, default: null },
    placeholder: { type: String, default: '请选择学年' },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'normal' },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    yearOptions() {
      if (this.options) return this.options
      const now = new Date().getFullYear()
      const start = now + this.forward
      const list = []
      for (let y = start; y > start - this.span; y--) {
        list.push({ label: `${y}-${y + 1} 学年`, value: `${y}-${y + 1}` })
      }
      return list
    }
  }
}
</script>
