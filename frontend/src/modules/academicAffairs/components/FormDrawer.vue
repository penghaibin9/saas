<template>
  <AppDrawer
    :visible="visible"
    :title="title"
    mode="modal"
    :size="fields.length > 6 ? 'large' : 'medium'"
    @update:visible="onClose"
  >
    <p v-if="note" class="afd-note">{{ note }}</p>
    <div v-for="f in fields" :key="f.key" class="afd-field">
      <label class="afd-label">{{ f.label }}<span v-if="f.required" class="afd-req">*</span></label>
      <AppSelect
        v-if="f.type === 'select'"
        :model-value="modelValue[f.key] ?? ''"
        :options="f.options || []"
        :placeholder="f.placeholder || '请选择'"
        @update:model-value="update(f.key, $event)"
      />
      <AppDatePicker
        v-else-if="f.type === 'date'"
        :model-value="modelValue[f.key] ?? ''"
        :placeholder="f.placeholder || '请选择日期'"
        @update:model-value="update(f.key, $event)"
      />
      <AppTextarea
        v-else-if="f.type === 'textarea'"
        :rows="f.rows || 3"
        :placeholder="f.placeholder || '请输入'"
        :model-value="modelValue[f.key] ?? ''"
        :disabled="f.disabled"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <AppNumberInput
        v-else-if="f.type === 'number'"
        :model-value="modelValue[f.key] ?? null"
        :min="f.min ?? -Infinity"
        :max="f.max ?? Infinity"
        :step="f.step ?? 1"
        :precision="f.precision ?? null"
        :controls="f.controls !== false"
        :placeholder="f.placeholder || '请输入'"
        :disabled="f.disabled"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <AppTextInput
        v-else
        :model-value="modelValue[f.key] ?? ''"
        :type="f.type === 'tel' ? 'tel' : 'text'"
        :placeholder="f.placeholder || '请输入'"
        :disabled="f.disabled"
        :maxlength="f.maxlength || 0"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <div v-if="errors[f.key]" class="afd-error">{{ errors[f.key] }}</div>
    </div>
    <template #footer>
      <AppButton variant="ghost" @click="onClose">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" @click="submit">{{ submitText }}</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * FormDrawer — 通用表单抽屉（模块局部组件，字段配置驱动，不写死业务字段）。
 * fields: [{ key, label, type: text|number|date|select|textarea, options?, required?, placeholder? }]
 */
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { AppSelect, AppDatePicker, AppTextInput, AppNumberInput, AppTextarea } from '@/components/common'

export default {
  name: 'AcademicFormDrawer',
  components: { AppDrawer, AppButton, AppSelect, AppDatePicker, AppTextInput, AppNumberInput, AppTextarea },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, required: true },
    note: { type: String, default: '' },
    fields: { type: Array, default: () => [] },
    modelValue: { type: Object, required: true },
    submitting: { type: Boolean, default: false },
    submitText: { type: String, default: '保存' }
  },
  emits: ['update:visible', 'update:modelValue', 'submit'],
  data() {
    return { errors: {} }
  },
  watch: {
    visible(v) {
      if (v) this.errors = {}
    }
  },
  methods: {
    onClose() {
      this.$emit('update:visible', false)
    },
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
      if (this.errors[key]) this.errors = { ...this.errors, [key]: '' }
    },
    submit() {
      const errors = {}
      for (const f of this.fields) {
        const v = this.modelValue[f.key]
        if (f.required && (v === undefined || v === null || String(v).trim() === '')) {
          errors[f.key] = `${f.label}为必填项`
        }
      }
      this.errors = errors
      if (Object.keys(errors).length) return
      this.$emit('submit')
    }
  }
}
</script>

<style scoped>
.afd-note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  background: var(--bg-section-blue);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin: 0 0 var(--space-4);
  line-height: var(--line-height-base);
}
.afd-field {
  margin-bottom: var(--space-4);
}
.afd-label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}
.afd-req {
  color: var(--danger-600);
  margin-left: 2px;
}
.afd-error {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
</style>
