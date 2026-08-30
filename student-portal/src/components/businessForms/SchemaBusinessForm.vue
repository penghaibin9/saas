<template>
  <form class="student-schema-form" @submit.prevent="submit">
    <div v-if="unsupported" class="unsupported">FORM_CLIENT_UNSUPPORTED：该表单请前往支持的 PC 入口。</div>
    <template v-else>
      <label v-for="entry in visibleFields" :key="entry.field.code">
        <span>{{ entry.field.label }}<b v-if="entry.state.required">*</b></span>
        <textarea v-if="entry.field.type === 'textarea'" :disabled="entry.state.readonly" :value="values[entry.field.code] || ''" @input="set(entry.field.code, $event.target.value)" />
        <select v-else-if="entry.field.type === 'select'" :disabled="entry.state.readonly" :multiple="entry.field.multiple" :value="values[entry.field.code]" @change="set(entry.field.code, selectValue($event, entry.field))">
          <option value="">请选择</option>
          <option v-for="option in entry.field.options || []" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
        </select>
        <button v-else-if="entry.field.type === 'file'" type="button" :disabled="entry.state.readonly" @click="$emit('request-file-center', entry.field)">从文件中心选择</button>
        <button v-else-if="entry.field.type === 'student-picker'" type="button" disabled>学生身份由服务端上下文确定</button>
        <input v-else :type="entry.field.type === 'number' ? 'number' : entry.field.type === 'datetime' ? 'datetime-local' : entry.field.type" :disabled="entry.state.readonly" :value="values[entry.field.code] ?? ''" @input="set(entry.field.code, entry.field.type === 'number' && $event.target.value !== '' ? Number($event.target.value) : $event.target.value)" />
        <small v-if="serverErrors[entry.field.code]" class="field-error">{{ serverErrors[entry.field.code] }}</small>
      </label>
      <button type="submit">提交</button>
    </template>
  </form>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { normalizeVersion, presentation } from './schemaRuntime.js'

const props = defineProps({
  formVersion: { type: Object, required: true },
  initialData: { type: Object, default: () => ({}) },
  serverErrors: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['submit', 'unsupported', 'request-file-center'])
const values = reactive({ ...props.initialData })
watch(() => props.initialData, value => {
  Object.keys(values).forEach(key => delete values[key])
  Object.assign(values, value || {})
}, { deep: true })
const version = computed(() => normalizeVersion(props.formVersion))
const unsupportedFields = computed(() => version.value.fields.filter(field => field.type === 'student-picker' && !field.readonly))
const unsupported = computed(() => !version.value.supportedClients.includes('STUDENT_PC') || unsupportedFields.value.length > 0)
const visibleFields = computed(() => version.value.fields.map(field => ({ field, state: presentation(field, values) })).filter(entry => entry.state.visible))
function set(code, value) { values[code] = value }
function selectValue(event, field) {
  if (!field.multiple) return event.target.value
  return Array.from(event.target.selectedOptions).map(option => option._value ?? option.value)
}
function submit() {
  if (unsupported.value) {
    emit('unsupported', { code: 'FORM_CLIENT_UNSUPPORTED', clientType: 'STUDENT_PC' })
    return
  }
  const submitted = Object.fromEntries(visibleFields.value
    .filter(entry => !entry.state.readonly && Object.prototype.hasOwnProperty.call(values, entry.field.code))
    .map(entry => [entry.field.code, values[entry.field.code]]))
  emit('submit', {
    formCode: version.value.formCode,
    formVersionId: version.value.versionId,
    schemaHash: version.value.schemaHash,
    clientType: 'STUDENT_PC',
    values: submitted,
  })
}
</script>

<style scoped>
.student-schema-form, label { display: grid; gap: 8px; }
.student-schema-form { max-width: 720px; gap: 18px; }
label b { color: #d92d20; margin-left: 3px; }
input, textarea, select, button { min-height: 42px; }
.unsupported { background: #fff3cd; color: #7a4d00; padding: 12px; border-radius: 8px; }
.field-error { color: #b42318; }
</style>
