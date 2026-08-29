<template>
  <form class="schema-business-form" @submit.prevent="submit">
    <div v-if="unsupported" class="unsupported" role="alert">FORM_CLIENT_UNSUPPORTED：请切换到受支持的 PC 端。</div>
    <template v-else>
      <label v-for="entry in visibleFields" :key="entry.field.code" class="field-row">
        <span>{{ entry.field.label }}<b v-if="entry.state.required">*</b></span>
        <textarea
          v-if="entry.field.type === 'textarea'"
          :value="draft[entry.field.code] || ''"
          :maxlength="entry.field.maxLength || entry.field.max_length"
          :disabled="entry.state.readonly"
          @input="setValue(entry.field.code, $event.target.value)"
        />
        <select
          v-else-if="entry.field.type === 'select'"
          :value="draft[entry.field.code]"
          :multiple="entry.field.multiple"
          :disabled="entry.state.readonly"
          @change="setValue(entry.field.code, selectValue($event, entry.field))"
        >
          <option value="">请选择</option>
          <option v-for="option in entry.field.options || []" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
        </select>
        <button v-else-if="entry.field.type === 'file'" type="button" :disabled="entry.state.readonly" @click="$emit('request-file-picker', entry.field)">从文件中心选择</button>
        <button v-else-if="entry.field.type === 'student-picker'" type="button" :disabled="entry.state.readonly" @click="$emit('request-student-picker', entry.field)">选择授权范围内学生</button>
        <input
          v-else
          :type="entry.field.type === 'number' ? 'number' : entry.field.type === 'datetime' ? 'datetime-local' : entry.field.type"
          :value="draft[entry.field.code] ?? ''"
          :min="entry.field.min ?? entry.field.min_value"
          :max="entry.field.max ?? entry.field.max_value"
          :maxlength="entry.field.maxLength || entry.field.max_length"
          :disabled="entry.state.readonly"
          @input="setValue(entry.field.code, entry.field.type === 'number' && $event.target.value !== '' ? Number($event.target.value) : $event.target.value)"
        />
        <small v-if="entry.field.helpText || entry.field.help_text">{{ entry.field.helpText || entry.field.help_text }}</small>
      </label>
      <button type="submit">提交到原业务</button>
    </template>
  </form>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { fieldPresentation, normalizeFormVersion, supportsClient } from '../schemaRuntime.js'

const props = defineProps({
  formVersion: { type: Object, required: true },
  modelValue: { type: Object, default: () => ({}) },
  clientType: { type: String, default: 'STAFF_PC' },
})
const emit = defineEmits(['update:modelValue', 'submit', 'unsupported', 'request-file-picker', 'request-student-picker'])
const draft = reactive({ ...props.modelValue })
watch(() => props.modelValue, value => {
  Object.keys(draft).forEach(key => delete draft[key])
  Object.assign(draft, value || {})
}, { deep: true })
const version = computed(() => normalizeFormVersion(props.formVersion))
const unsupported = computed(() => !supportsClient(props.formVersion, props.clientType))
const visibleFields = computed(() => version.value.fields
  .map(field => ({ field, state: fieldPresentation(field, draft) }))
  .filter(entry => entry.state.visible))
function setValue(code, value) {
  draft[code] = value
  emit('update:modelValue', { ...draft })
}
function selectValue(event, field) {
  if (!field.multiple) return event.target.value
  return Array.from(event.target.selectedOptions).map(option => option._value ?? option.value)
}
function submit() {
  if (unsupported.value) {
    emit('unsupported', { code: 'FORM_CLIENT_UNSUPPORTED', clientType: props.clientType })
    return
  }
  const values = Object.fromEntries(visibleFields.value
    .filter(entry => !entry.state.readonly && Object.prototype.hasOwnProperty.call(draft, entry.field.code))
    .map(entry => [entry.field.code, draft[entry.field.code]]))
  emit('submit', {
    formCode: version.value.formCode,
    formVersionId: version.value.versionId,
    schemaHash: version.value.schemaHash,
    clientType: props.clientType,
    values,
  })
}
</script>

<style scoped>
.schema-business-form { display: grid; gap: 16px; }
.field-row { display: grid; gap: 6px; }
.field-row b { color: #d92d20; margin-left: 3px; }
input, textarea, select, button { min-height: 38px; }
.unsupported { padding: 12px; color: #b42318; background: #fee4e2; border-radius: 8px; }
</style>
