<template>
  <input
    :value="modelValue"
    type="date"
    :min="effectiveMin || undefined"
    :max="effectiveMax || undefined"
    :disabled="disabled"
    :aria-label="ariaLabel || label || placeholder || '选择日期'"
    @input="updateValue"
    @change="emit('change', $event.target.value)"
  />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  min: { type: String, default: '' },
  max: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' },
  ariaLabel: { type: String, default: '' },
  placeholder: { type: String, default: '请选择日期' },
  role: { type: String, default: '' },
  startValue: { type: String, default: '' },
  endValue: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'change'])

// 与管理端 AppDatePicker 的起止日期约束保持同一调用口径。
const effectiveMin = computed(() => props.min || (props.role === 'end' ? props.startValue : ''))
const effectiveMax = computed(() => props.max || (props.role === 'start' ? props.endValue : ''))

function updateValue(event) {
  emit('update:modelValue', event.target.value || '')
}
</script>
