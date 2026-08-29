<template>
  <view class="schema-form">
    <view v-if="unsupported" class="unsupported">
      <text>FORM_CLIENT_UNSUPPORTED</text>
      <text>当前小程序不支持此表单的完整字段，请前往 PC 办理。</text>
    </view>
    <template v-else>
      <view v-for="entry in visibleFields" :key="entry.field.code" class="field">
        <text class="label">{{ entry.field.label }}<text v-if="entry.state.required" class="required">*</text></text>
        <textarea v-if="entry.field.type === 'textarea'" :disabled="entry.state.readonly" :value="values[entry.field.code] || ''" @input="set(entry.field.code, $event.detail.value)" />
        <picker v-else-if="entry.field.type === 'select'" :disabled="entry.state.readonly" :range="entry.field.options || []" range-key="label" @change="select(entry.field, $event.detail.value)">
          <view class="picker-value">{{ selectLabel(entry.field) || '请选择' }}</view>
        </picker>
        <button v-else-if="entry.field.type === 'file'" size="mini" :disabled="entry.state.readonly" @click="$emit('request-file-center', entry.field)">从文件中心选择</button>
        <picker v-else-if="entry.field.type === 'date' || entry.field.type === 'datetime'" :mode="entry.field.type === 'date' ? 'date' : 'time'" :disabled="entry.state.readonly" @change="set(entry.field.code, $event.detail.value)">
          <view class="picker-value">{{ values[entry.field.code] || '请选择' }}</view>
        </picker>
        <input v-else :type="entry.field.type === 'number' ? 'number' : 'text'" :disabled="entry.state.readonly" :value="values[entry.field.code] ?? ''" @input="set(entry.field.code, entry.field.type === 'number' && $event.detail.value !== '' ? Number($event.detail.value) : $event.detail.value)" />
      </view>
      <button type="primary" @click="submit">提交</button>
    </template>
  </view>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { normalizeVersion, presentation } from './schemaRuntime.js'

const MOBILE_FIELD_TYPES = new Set(['text', 'textarea', 'number', 'select', 'date', 'file'])
const props = defineProps({
  formVersion: { type: Object, required: true },
  initialData: { type: Object, default: () => ({}) },
  clientType: { type: String, required: true, validator: value => ['TEACHER_MINIAPP', 'STUDENT_MINIAPP'].includes(value) },
})
const emit = defineEmits(['submit', 'unsupported', 'request-file-center'])
const values = reactive({ ...props.initialData })
watch(() => props.initialData, value => {
  Object.keys(values).forEach(key => delete values[key])
  Object.assign(values, value || {})
}, { deep: true })
const version = computed(() => normalizeVersion(props.formVersion))
const unsupportedFields = computed(() => version.value.fields.filter(field => (
  !MOBILE_FIELD_TYPES.has(field.type) || (field.type === 'select' && field.multiple)
)))
const unsupported = computed(() => !version.value.supportedClients.includes(props.clientType) || unsupportedFields.value.length > 0)
const visibleFields = computed(() => version.value.fields.map(field => ({ field, state: presentation(field, values) })).filter(entry => entry.state.visible))
function set(code, value) { values[code] = value }
function select(field, index) {
  const option = (field.options || [])[Number(index)]
  if (option) set(field.code, option.value)
}
function selectLabel(field) {
  return (field.options || []).find(option => option.value === values[field.code])?.label || ''
}
function submit() {
  if (unsupported.value) {
    emit('unsupported', {
      code: 'FORM_CLIENT_UNSUPPORTED',
      clientType: props.clientType,
      unsupportedFields: unsupportedFields.value.map(field => field.code),
      fallback: 'PC',
    })
    return
  }
  const submitted = Object.fromEntries(visibleFields.value
    .filter(entry => !entry.state.readonly && Object.prototype.hasOwnProperty.call(values, entry.field.code))
    .map(entry => [entry.field.code, values[entry.field.code]]))
  emit('submit', {
    formCode: version.value.formCode,
    formVersionId: version.value.versionId,
    schemaHash: version.value.schemaHash,
    clientType: props.clientType,
    values: submitted,
  })
}
</script>

<style scoped>
.schema-form, .field, .unsupported { display: flex; flex-direction: column; gap: 16rpx; }
.field { padding: 20rpx 0; border-bottom: 1rpx solid #eef1f5; }
.label { color: #344054; font-size: 28rpx; }
.required { color: #d92d20; margin-left: 4rpx; }
.picker-value, input, textarea { min-height: 72rpx; padding: 12rpx; background: #f8fafc; border-radius: 10rpx; }
.unsupported { padding: 24rpx; color: #b42318; background: #fee4e2; border-radius: 12rpx; }
</style>
